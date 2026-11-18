"""Provision durable analysis checkpoints and revision IDs."""

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import Column, Integer

from alembic import op
from app.db.checkpoints import postgres_url

revision = "318b3cb5518a"
down_revision = "b412ea782b4f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", Column("checkpoint_epoch", Integer(), server_default="0", nullable=False))
    uri = postgres_url()
    if uri:
        with PostgresSaver.from_conn_string(uri) as storage:
            storage.setup()


def downgrade():
    op.drop_column("jobs", "checkpoint_epoch")
    if postgres_url():
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints", "checkpoint_migrations"):
            op.drop_table(table)
