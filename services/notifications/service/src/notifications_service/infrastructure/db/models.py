"""Tables owned by this service live in its own schema (rules D-1, D-2)."""

import sqlalchemy as sa

from platform_core.db import make_metadata
from platform_events import make_outbox_table

SCHEMA = "notifications"

metadata = make_metadata(SCHEMA)
outbox_table = make_outbox_table(metadata)

# The delivery LOG: who we tried to reach, how, and what happened. Never the message body, never the full recipient.
deliveries_table = sa.Table(
    "deliveries",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("channel", sa.String(16), nullable=False),
    sa.Column("recipient_masked", sa.String(320), nullable=False),
    sa.Column("recipient_digest", sa.String(64), nullable=False),
    sa.Column("template", sa.String(64), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("provider", sa.String(32), nullable=True),
    sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("error_code", sa.String(64), nullable=True),
    sa.Column("idempotency_key", sa.String(128), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Index("uq_deliveries_idempotency_key", "idempotency_key", unique=True),
    sa.Index("ix_deliveries_digest_created", "recipient_digest", "created_at"),
)
