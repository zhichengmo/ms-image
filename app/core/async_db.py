from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, declared_attr
from contextlib import asynccontextmanager

from app.core.config import settings

# Primary database connection
DATABASE_URL = (f"mysql+aiomysql://"
                f"{settings.MYSQL_USER}:{settings.MYSQL_PW}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}"
                f"/{settings.MYSQL_DB}")

# MS_HD database connection (for integration with HD service)
MS_HD_DATABASE_URL = (f"mysql+aiomysql://"
                     f"{settings.MYSQL_HD_USER}:{settings.MYSQL_HD_PW}@{settings.MYSQL_HD_HOST}:{settings.MYSQL_HD_PORT}"
                     f"/{settings.MYSQL_HD_DB}")

# Create database engines
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    echo_pool=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=5,
    connect_args=(
        {"unix_socket": settings.MYSQL_UNIX_SOCKET}
        if settings.MYSQL_UNIX_SOCKET.strip()
        else {}
    )
)

async_engine_hd = create_async_engine(
    MS_HD_DATABASE_URL,
    echo=False,
    echo_pool=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=5,
    connect_args=(
        {"unix_socket": settings.MYSQL_HD_UNIX_SOCKET}
        if settings.MYSQL_HD_UNIX_SOCKET.strip()
        else {}
    )
)

# Create database sessions
session_factory = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    expire_on_commit=True
)

session_factory_hd = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine_hd,
    expire_on_commit=True
)


class BaseModel(AsyncAttrs, DeclarativeBase):
    """
    基础模型类，提供通用功能
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """
        将表名改为小写
        如果有自定义表名就取小写类名
        """
        model_name = cls.__name__
        ls = []
        for index, char in enumerate(model_name):
            if char.isupper() and index != 0:
                ls.append("_")
            ls.append(char)
        return "".join(ls).lower()


# 为了保持向后兼容性，将 Base 作为 BaseModel 的别名
Base = BaseModel


class HdBase(AsyncAttrs, DeclarativeBase):
    """
    MS_HD 数据库的基础模型类（HD服务集成）
    """
    __abstract__ = True

    @declared_attr.directive
    def __tablename__(cls) -> str:
        model_name = cls.__name__
        ls = []
        for index, char in enumerate(model_name):
            if char.isupper() and index != 0:
                ls.append("_")
            ls.append(char)
        return "".join(ls).lower()


# Database dependencies
async def get_async_session() -> AsyncSession:
    """
    获取主数据库会话
    """
    async with session_factory() as session:
        async with session.begin():
            yield session


async def get_async_session_hd() -> AsyncSession:
    """
    获取 MS_HD 数据库会话（HD服务集成）
    """
    async with session_factory_hd() as session:
        async with session.begin():
            yield session


@asynccontextmanager
async def db_getter() -> AsyncSession:
    """
    用于手动打开主数据库session（async with）
    """
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise e
    finally:
        await session.close()


@asynccontextmanager
async def db_getter_hd() -> AsyncSession:
    """
    获取 MS_HD 数据库会话
    使用异步上下文管理器模式，确保会话的正确创建和清理
    """
    session = session_factory_hd()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise e
    finally:
        await session.close()
