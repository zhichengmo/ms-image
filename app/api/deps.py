import jwt
import os
import rsa
import base64
import json
from datetime import datetime
from fastapi import Depends, Header, HTTPException, status, Security
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer
from typing import Optional

from app.core.config import settings


auth_domain = os.getenv('AUTH_DOMAIN')
http_bearer = HTTPBearer()


# 创建 HTTPBasic 安全实例
security = HTTPBasic()


def basic_auth(
        credentials: HTTPBasicCredentials = Security(security)
) -> bool:
    """
    Basic Auth 认证依赖注入方法
    """
    # 获取用户名和密码
    username = credentials.username
    password = credentials.password

    # 这里可以添加你的认证逻辑，比如验证用户名和密码是否正确
    # 示例：验证用户名和密码是否匹配
    if username != "admin" or password != "password":
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    # 认证成功，可以返回用户信息或其他数据
    return True


def get_jwt_data(
    data: str = Depends(http_bearer)
) -> dict:

    try:
        token = data.credentials

        # 根据算法选择对应的密钥
        if settings.ALGORITHM == "RS256":
            # 读取 RSA 公钥文件
            try:
                with open("rsa_public.pem", "r") as f:
                    public_key = f.read()
                decode_key = public_key
            except FileNotFoundError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="RSA public key file not found"
                )
        else:
            # 使用对称密钥 (HS256)
            decode_key = settings.SECRET_KEY

        payload = jwt.decode(
            token,
            decode_key,
            algorithms=[settings.ALGORITHM]
        )
    except jwt.InvalidAlgorithmError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Algorithm not supported: {str(e)}"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"JWT error: {str(e)}"
        )
    return payload


def authorized_user(
    jwt_data: dict = Depends(get_jwt_data)
) -> str:
    try:
        # 根据JWT token格式提取用户ID
        if 'sub' in jwt_data and isinstance(jwt_data['sub'], dict):
            user_uuid = jwt_data['sub'].get('id')
        elif 'identity' in jwt_data:
            identity = jwt_data['identity']
            user_uuid = identity.get('id') if isinstance(identity, dict) else identity
        else:
            user_uuid = jwt_data.get('sub')

        if not user_uuid:
            raise ValueError("User ID not found in JWT token")

        # 确保返回字符串类型
        return str(user_uuid)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Failed to extract user ID from JWT: {str(e)}"
        )


def is_internal_user(
    jwt_data: dict = Depends(get_jwt_data)
) -> bool:
    try:
        identity = jwt_data['identity']
    except:
        identity = jwt_data['sub']
    if not identity['is_internal']:
        raise HTTPException(
            status_code=403,
            detail='You are not internal user'
        )
    return identity['is_internal']


def is_tester_user(
    jwt_data: dict = Depends(get_jwt_data)
) -> bool:
    try:
        identity = jwt_data['sub']
        is_tester = identity['is_tester']
    except:
        is_tester = False
    return is_tester


def ms_api_key_verified(
    authorization: Optional[str] = Header(None)
):
    if not authorization:
        raise HTTPException(
            status_code=400,
            detail='Missing authorization headers.'
        )
    try:
        private_key = rsa.PrivateKey.load_pkcs1(settings.API_PRIVATE_KEY)
        decrypted_data = rsa.decrypt(base64.b64decode(authorization), private_key).decode()
        decrypted_json = json.loads(decrypted_data)
        key_time = int(decrypted_json['timestamp'])
    except:
        raise HTTPException(
            status_code=401,
            detail=f'Invalid API key: {authorization}'
        )
    now_time = int(datetime.utcnow().timestamp())
    # APi KEY过期时间五分钟
    if now_time - key_time <= 300:
        return True
    else:
        raise HTTPException(
            status_code=401,
            detail='The API key is expired.'
        )