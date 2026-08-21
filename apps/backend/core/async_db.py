from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, declared_attr
from contextlib import asynccontextmanager

from apps.backend.core.config import settings

# Primary database connection
DATABASE_URL = (f"mysql+aiomysql://"
                f"{settings.MYSQL_USER}:{settings.MYSQL_PW}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}"
                f"/{settings.MYSQL_DB}")

# Isolated Evaluation database connection.  Empty connection overrides
# intentionally inherit primary MySQL transport settings while keeping a
# separate database name; production may supply distinct credentials/host.
_evaluation_database = settings.MYSQL_EVALUATION_DB.strip()
if not _evaluation_database or _evaluation_database == settings.MYSQL_DB.strip():
    raise RuntimeError("evaluation_database_isolation_invalid")
_evaluation_user = settings.MYSQL_EVALUATION_USER.strip() or settings.MYSQL_USER
_evaluation_password = settings.MYSQL_EVALUATION_PW or settings.MYSQL_PW
_evaluation_host = settings.MYSQL_EVALUATION_HOST.strip() or settings.MYSQL_HOST
_evaluation_port = settings.MYSQL_EVALUATION_PORT.strip() or settings.MYSQL_PORT
_evaluation_unix_socket = (
    settings.MYSQL_EVALUATION_UNIX_SOCKET.strip()
    or settings.MYSQL_UNIX_SOCKET.strip()
)
EVALUATION_DATABASE_URL = (f"mysql+aiomysql://"
                           f"{_evaluation_user}:{_evaluation_password}@{_evaluation_host}:{_evaluation_port}"
                           f"/{_evaluation_database}")

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

evaluation_async_engine = create_async_engine(
    EVALUATION_DATABASE_URL,
    echo=False,
    echo_pool=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=5,
    connect_args=(
        {"unix_socket": _evaluation_unix_socket}
        if _evaluation_unix_socket
        else {}
    )
)

async_engine_hd = None
session_factory_hd = None


def _initialize_hd_database() -> None:
    """Initialize the optional HD pool only when explicitly enabled."""

    global async_engine_hd, session_factory_hd
    if async_engine_hd is not None:
        return
    if not settings.MYSQL_HD_ENABLED:
        raise RuntimeError("ms_hd_database_disabled")

    ms_hd_database_url = (
        "mysql+aiomysql://"
        f"{settings.MYSQL_HD_USER}:{settings.MYSQL_HD_PW}@"
        f"{settings.MYSQL_HD_HOST}:{settings.MYSQL_HD_PORT}/{settings.MYSQL_HD_DB}"
    )
    async_engine_hd = create_async_engine(
        ms_hd_database_url,
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
        ),
    )
    session_factory_hd = async_sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=async_engine_hd,
        expire_on_commit=True,
    )


# Create database sessions
session_factory = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    expire_on_commit=True
)

evaluation_session_factory = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=evaluation_async_engine,
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


async def get_evaluation_async_session() -> AsyncSession:
    """获取隔离的 Evaluation 控制面数据库会话。"""
    async with evaluation_session_factory() as session:
        async with session.begin():
            yield session


async def get_explicit_evaluation_transaction_session() -> AsyncSession:
    """Yield an Evaluation session whose short transactions are caller-owned."""
    async with evaluation_session_factory() as session:
        try:
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()


async def get_explicit_transaction_session() -> AsyncSession:
    """Yield a session whose transaction scopes are owned by the endpoint.

    Storage workflows use this dependency to commit a short database phase,
    perform OSS I/O without a transaction, and then open a new short phase.
    Existing endpoints keep using ``get_async_session`` unchanged.
    """

    async with session_factory() as session:
        try:
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()


async def get_async_session_hd() -> AsyncSession:
    """
    获取 MS_HD 数据库会话（HD服务集成）
    """
    _initialize_hd_database()
    assert session_factory_hd is not None
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
async def evaluation_db_getter() -> AsyncSession:
    """Evaluation 数据库手动 session 上下文。"""
    session = evaluation_session_factory()
    try:
        yield session
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise exc
    finally:
        await session.close()


@asynccontextmanager
async def db_getter_hd() -> AsyncSession:
    """
    获取 MS_HD 数据库会话
    使用异步上下文管理器模式，确保会话的正确创建和清理
    """
    _initialize_hd_database()
    assert session_factory_hd is not None
    session = session_factory_hd()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise e
    finally:
        await session.close()
