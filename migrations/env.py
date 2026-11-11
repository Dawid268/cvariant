import asyncio
import importlib
import pkgutil
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.modules
from app.core.db import Base
from app.settings import get_settings

config = context.config
if config.config_file_name is not None:
    # Keep loggers created before migrations ran (e.g. when tests run migrations in-process);
    # the default would silently disable every application logger.
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def import_all_models() -> None:
    """Import every app/modules/<name>/models.py so autogenerate sees all tables."""
    for module in pkgutil.iter_modules(app.modules.__path__):
        try:
            importlib.import_module(f"{app.modules.__name__}.{module.name}.models")
        except ModuleNotFoundError:
            continue


import_all_models()
target_metadata = Base.metadata
database_url = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
