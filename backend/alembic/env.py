from sqlalchemy import create_engine, pool

from alembic import context
from app.core.config import settings
from app.db import models
from app.db.session import Base

assert models


def run():
    url = settings().database_url
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    def include_name(name, kind, _parents):
        if kind != "table":
            return True
        return name not in {"checkpoints", "checkpoint_writes", "checkpoint_blobs", "checkpoint_migrations"}

    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=Base.metadata, compare_type=True, include_name=include_name
        )
        with context.begin_transaction():
            context.run_migrations()


run()
