from logging.config import fileConfig

import sqlalchemy as sa
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

import app.models  # noqa: F401  registers all table models on SQLModel.metadata
from alembic import context
from app.core.config import get_settings

config = context.config
# Tests pass the test database URL explicitly; otherwise use DATABASE_URL.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def render_item(type_, obj, autogen_context):
    """Render non-native enums as VARCHAR. The model's CHECK constraint is rendered
    separately; rendering sa.Enum(create_constraint=True) would create duplicates."""
    if type_ == "type" and isinstance(obj, sa.Enum) and not obj.native_enum:
        return f"sa.String(length={obj.length})"
    # Each enum CHECK is rendered twice: once with the naming-convention name, once with
    # the bare enum name. Keep only the convention-named one.
    if (
        type_ == "check"
        and getattr(obj, "_type_bound", False)
        and not isinstance(obj.name, sa.sql.elements.conv)
    ):
        return None
    return False


def run_migrations_offline() -> None:
    """Emit migration SQL without connecting to the database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        render_item=render_item,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the database in DATABASE_URL."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_item=render_item
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
