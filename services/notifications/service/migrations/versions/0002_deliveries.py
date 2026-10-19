"""deliveries: the delivery log

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SCHEMA = "notifications"  # frozen snapshot: migrations never import application code


def upgrade() -> None:
    op.create_table(
        "deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("recipient_masked", sa.String(length=320), nullable=False),
        sa.Column("recipient_digest", sa.String(length=64), nullable=False),
        sa.Column("template", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_deliveries"),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_deliveries_idempotency_key",
        "deliveries",
        ["idempotency_key"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_deliveries_digest_created",
        "deliveries",
        ["recipient_digest", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_deliveries_digest_created", table_name="deliveries", schema=SCHEMA)
    op.drop_index("uq_deliveries_idempotency_key", table_name="deliveries", schema=SCHEMA)
    op.drop_table("deliveries", schema=SCHEMA)
