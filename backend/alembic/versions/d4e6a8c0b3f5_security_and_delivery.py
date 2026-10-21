"""two-factor sign-in, session invalidation, email delivery counts

Revision ID: d4e6a8c0b3f5
Revises: c3d5f7a9b2e4
Create Date: 2026-10-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e6a8c0b3f5"
down_revision: Union[str, None] = "c3d5f7a9b2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("totp_secret", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("totp_last_step", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("recovery_codes", sa.Text(), nullable=True))
    op.add_column("broadcast_logs", sa.Column("delivered_count", sa.Integer(), nullable=True))
    op.add_column("broadcast_logs", sa.Column("failed_count", sa.Integer(), nullable=True))
    op.add_column("broadcast_logs", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    for col in ("last_error", "failed_count", "delivered_count"):
        op.drop_column("broadcast_logs", col)
    for col in ("recovery_codes", "totp_last_step", "totp_enabled", "totp_secret", "session_version"):
        op.drop_column("users", col)
