"""
用户数据访问层示例 - UserDal
这是一个完整的DAL实现示例，展示了如何正确使用DalBase基类
"""

from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.crud import DalBase
# from app.models.user import User  # 需要先创建User模型
# from app.schemas.user import UserCreate, UserUpdate, UserResponse  # 需要先创建相关Schema


class UserDal(DalBase):
    """用户数据访问层"""

    def __init__(self, db: AsyncSession):
        """
        初始化UserDal
        Args:
            db: AsyncSession - 异步数据库会话
        """
        # 注意：需要先创建User模型才能使用
        # super().__init__(db=db, model=User)
        super().__init__(db=db, model=None)  # 临时使用None，实际应使用User模型

    async def create_user(self, user_data: dict) -> dict:
        """
        创建新用户
        Args:
            user_data: UserCreate - 用户创建数据
        Returns:
            dict: 创建的用户信息
        """
        # 使用 model_dump() 转换Pydantic模型为字典
        # return await self.create_data(user_data.model_dump(), v_schema=UserResponse)
        return await self.create_data(user_data)

    async def update_user(self, user_id: int, user_data: dict) -> dict:
        """
        更新用户信息
        Args:
            user_id: int - 用户ID
            user_data: UserUpdate - 用户更新数据
        Returns:
            dict: 更新后的用户信息
        """
        # 使用 exclude_unset=True 只更新有变化的字段
        # update_data = user_data.model_dump(exclude_unset=True)
        update_data = user_data
        if not update_data:
            # 如果没有需要更新的数据，返回原数据
            return await self.get_data(user_id)
        return await self.put_data(user_id, update_data)

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """
        根据邮箱获取用户
        Args:
            email: str - 用户邮箱
        Returns:
            Optional[dict]: 用户信息，不存在则返回None
        """
        return await self.get_data(email=email)

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """
        根据用户名获取用户
        Args:
            username: str - 用户名
        Returns:
            Optional[dict]: 用户信息，不存在则返回None
        """
        return await self.get_data(username=username)

    async def get_active_users(self, page: int = 1, limit: int = 10) -> List[dict]:
        """
        获取活跃用户列表
        Args:
            page: int - 页码
            limit: int - 每页数量
        Returns:
            List[dict]: 用户列表
        """
        return await self.get_datas(
            page=page,
            limit=limit,
            is_active=True,  # 假设有is_active字段
            is_del=0  # 假设有软删除字段
        )

    async def delete_user(self, user_id: int, soft: bool = True) -> None:
        """
        删除用户（支持软删除）
        Args:
            user_id: int - 用户ID
            soft: bool - 是否软删除，默认True
        """
        if soft:
            # 软删除，设置is_del字段
            await self.put_data(user_id, {"is_del": 1})
        else:
            # 硬删除
            await self.delete_datas([user_id])

    async def get_users_by_role(self, role: str) -> List[dict]:
        """
        根据角色获取用户列表
        Args:
            role: str - 用户角色
        Returns:
            List[dict]: 该角色的用户列表
        """
        return await self.get_datas(role=role, is_del=0)


# 使用示例 - 在Service层中的使用方式
class UserService:
    """用户业务逻辑层示例"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_dal = UserDal(db)  # 在构造函数中初始化DAL

    async def create_user(self, user_data: dict):
        """创建用户业务逻辑"""
        # 可以在这里添加业务逻辑验证
        existing_user = await self.user_dal.get_user_by_email(user_data.get('email'))
        if existing_user:
            raise ValueError("邮箱已存在")

        return await self.user_dal.create_user(user_data)

    async def get_user_profile(self, user_id: int):
        """获取用户资料"""
        user = await self.user_dal.get_data(user_id)
        if not user:
            raise ValueError("用户不存在")
        return user


# 函数式使用方式示例
async def get_user_by_id_func(user_id: int, db: AsyncSession) -> Optional[dict]:
    """
    函数式获取用户信息
    Args:
        user_id: int - 用户ID
        db: AsyncSession - 数据库会话
    Returns:
        Optional[dict]: 用户信息
    """
    user_dal = UserDal(db)
    return await user_dal.get_data(user_id)


# API层使用示例（依赖注入方式）
"""
# app/api/deps.py
from app.core.async_db import get_db_session

async def get_user_service(db: AsyncSession = Depends(get_db_session)) -> UserService:
    return UserService(db)

# app/api/endpoints/users.py
@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    user_service: UserService = Depends(get_user_service)
):
    return await user_service.create_user(user_data)
"""