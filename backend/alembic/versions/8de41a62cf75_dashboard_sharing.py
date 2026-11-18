"""Add revocable dashboard links and durable job recovery counters."""

from sqlalchemy import Column, Integer, String

from alembic import op

revision = "8de41a62cf75"
down_revision = "318b3cb5518a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", Column("recovery_count", Integer(), server_default="0", nullable=False))
    op.add_column("jobs", Column("failure_code", String(32), nullable=True))
    op.add_column("dashboards", Column("share_digest", String(64), nullable=True))
    op.create_index("ix_dashboards_share_digest", "dashboards", ["share_digest"], unique=True)


def downgrade():
    op.drop_column("jobs", "failure_code")
    op.drop_column("jobs", "recovery_count")
    op.drop_index("ix_dashboards_share_digest", table_name="dashboards")
    op.drop_column("dashboards", "share_digest")
