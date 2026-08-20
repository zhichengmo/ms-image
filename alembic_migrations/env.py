from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy.engine import URL
from sqlalchemy import pool

from alembic import context
import sys
from pathlib import Path

# The migration directory remains at repository root while the sole Runtime
# source (and its ``app`` import package) lives below services/runtime.
REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = REPO_ROOT / "services" / "runtime"
for import_root in (RUNTIME_ROOT, REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

# Import your models
from app.core.async_db import BaseModel
from app.core.config import settings
# Import every model package explicitly so autogenerate sees the same metadata
# used by the runtime.  This import is metadata-only; it does not create/drop
# tables and does not execute a migration.
import app.models  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Never use the repository's historical hard-coded password.  Resolve the
# Alembic URL from the same environment source as the application and build it
# with SQLAlchemy URL encoding so special characters remain valid.
config.set_main_option(
    "sqlalchemy.url",
    str(
        URL.create(
            "mysql+pymysql",
            username=settings.MYSQL_USER,
            password=settings.MYSQL_PW,
            host=settings.MYSQL_HOST,
            port=int(settings.MYSQL_PORT),
            database=settings.MYSQL_DB,
        )
    ),
)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = BaseModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
