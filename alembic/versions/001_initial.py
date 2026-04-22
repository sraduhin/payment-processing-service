"""initial

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'currency_enum') THEN
                CREATE TYPE currency_enum AS ENUM ('RUB', 'USD', 'EUR');
            END IF;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_status_enum') THEN
                CREATE TYPE payment_status_enum AS ENUM ('pending', 'succeeded', 'failed');
            END IF;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'outbox_status_enum') THEN
                CREATE TYPE outbox_status_enum AS ENUM ('pending', 'sent', 'failed');
            END IF;
        END $$
    """)

    op.execute("""
        CREATE TABLE payments (
            id UUID PRIMARY KEY,
            amount NUMERIC(12, 2) NOT NULL,
            currency currency_enum NOT NULL,
            description TEXT NOT NULL,
            metadata JSONB,
            status payment_status_enum NOT NULL DEFAULT 'pending',
            idempotency_key UUID NOT NULL UNIQUE,
            webhook_url TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE TABLE outbox (
            id UUID PRIMARY KEY,
            payment_id UUID NOT NULL REFERENCES payments(id),
            status outbox_status_enum NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("payments")
    sa.Enum(name="outbox_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="payment_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="currency_enum").drop(op.get_bind(), checkfirst=True)
