from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import URL


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.backend.core.async_db import EvaluationBaseModel  # noqa: E402
from apps.backend.core.config import settings  # noqa: E402
import apps.backend.models  # noqa: E402,F401


evaluation_database = settings.MYSQL_EVALUATION_DB.strip()
if not evaluation_database or evaluation_database == settings.MYSQL_DB.strip():
    raise RuntimeError("evaluation_database_isolation_invalid")

evaluation_user = settings.MYSQL_EVALUATION_USER.strip() or settings.MYSQL_USER
evaluation_password = settings.MYSQL_EVALUATION_PW or settings.MYSQL_PW
evaluation_host = settings.MYSQL_EVALUATION_HOST.strip() or settings.MYSQL_HOST
evaluation_port = settings.MYSQL_EVALUATION_PORT.strip() or settings.MYSQL_PORT
evaluation_socket = (
    settings.MYSQL_EVALUATION_UNIX_SOCKET.strip()
    or settings.MYSQL_UNIX_SOCKET.strip()
)

config = context.config
config.set_main_option(
    "sqlalchemy.url",
    URL.create(
        "mysql+pymysql",
        username=evaluation_user,
        password=evaluation_password,
        host=evaluation_host,
        port=int(evaluation_port),
        database=evaluation_database,
    ).render_as_string(hide_password=False),
)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = EvaluationBaseModel.metadata


def _context_options() -> dict[str, object]:
    return {
        "target_metadata": target_metadata,
        "compare_type": True,
        "compare_server_default": True,
    }


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_context_options(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connect_args: dict[str, str] = {"init_command": "SET time_zone = '+00:00'"}
    if evaluation_socket:
        connect_args["unix_socket"] = evaluation_socket
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, **_context_options())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
