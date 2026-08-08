from pydantic import DirectoryPath
from pydantic_settings import BaseSettings
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"

    APPLICATION_HOST: str = "localhost"
    APPLICATION_NAME: str = "Ms Image Service"
    APPLICATION_PORT: int = 8000

    ENV: str = "dev"

    GUNICORN_ERROR_LOG_PATH: str = "./logs/gunicorn_error.log"
    LOG_PATH: str = "./logs/"

    MONGO_AUTH_SOURCE: str = "admin"
    MONGO_DB: str = "ms_image"
    MONGO_HOST: str = "localhost"
    MONGO_PASSWORD: str = ""
    MONGO_PORT: str = "27017"
    MONGO_USER: str = "admin"

    # Primary Database settings
    MYSQL_DB: str = "ms_image"
    MYSQL_HOST: str = "localhost"
    MYSQL_PW: str = "password"
    MYSQL_USER: str = "root"
    MYSQL_PORT: str = "3306"

    # MS_HD Database settings (optional for HD service integration)
    MYSQL_HD_DB: str = "ms_hd"
    MYSQL_HD_HOST: str = "localhost"
    MYSQL_HD_PW: str = "password"
    MYSQL_HD_USER: str = "root"
    MYSQL_HD_PORT: str = "3306"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    ALGORITHM: str = "RS256"
    SECRET_KEY: str = ""
    API_PRIVATE_KEY: str = ""

    # Admin JWT settings
    ADMIN_ALGORITHM: str = "HS256"
    ADMIN_SECRET_KEY: str = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 根据算法类型加载密钥
        if self.ALGORITHM == "RS256":
            try:
                with open('rsa_public.pem', 'r') as f:
                    self.SECRET_KEY = f.read()
            except FileNotFoundError:
                print("Warning: rsa_public.pem not found, JWT verification may fail")
                self.SECRET_KEY = ""
        # HS256算法使用环境变量中的SECRET_KEY

    AUTH_DOMAIN: str = "localhost"

    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PASSWORD: str = "password"
    RABBITMQ_PORT: str = "5672"
    RABBITMQ_USERNAME: str = "admin"
    RABBITMQ_VIRTUAL_HOST: str = "/"

    PROJECT_ENV: str = "development"

    # 阿里云推送服务配置
    ALIBABA_ACCESS_KEY_ID: str = ""
    ALIBABA_ACCESS_KEY_SECRET: str = ""
    ALIBABA_PUSH_APP_KEY_IOS: str = ""
    ALIBABA_PUSH_APP_KEY_ANDROID: str = ""

    # 阿里云OSS配置
    OSS_ACCESS_KEY_ID: str = ""
    OSS_ACCESS_KEY_SECRET: str = ""
    OSS_BUCKET_NAME: str = ""
    OSS_UPLOAD_ENDPOINT: str = ""
    OSS_ENDPOINT: str = ""

    class Config:
        case_sensitive = True
        env_file = '.env'
        env_file_encoding = 'utf-8'


settings = Settings()