"""ops hardening: payment methods, review metadata, idempotent ROI, email verification

Revision ID: b2c4e6f80a11
Revises: dd17e3482396
Create Date: 2026-10-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c4e6f80a11"
down_revision: Union[str, None] = "dd17e3482396"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset", sa.String(20), nullable=False),
        sa.Column("network", sa.String(50), nullable=False),
        sa.Column("deposit_address", sa.String(255), nullable=True),
        sa.Column("deposit_memo", sa.String(255), nullable=True),
        sa.Column("deposit_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("withdraw_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("min_deposit", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("min_withdrawal", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("withdrawal_fee", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # users
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("kyc_rejection_reason", sa.Text(), nullable=True))
    op.alter_column("users", "kyc_document_url", type_=sa.Text(), existing_type=sa.String(500))

    # transactions
    op.alter_column("transactions", "proof_image_url", type_=sa.Text(), existing_type=sa.String(500))
    op.add_column("transactions", sa.Column("payment_method_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_tx_payment_method", "transactions", "payment_methods", ["payment_method_id"], ["id"])
    op.add_column("transactions", sa.Column("asset", sa.String(20), nullable=True))
    op.add_column("transactions", sa.Column("network", sa.String(50), nullable=True))
    op.add_column("transactions", sa.Column("fee", sa.Numeric(20, 8), nullable=True))
    op.add_column("transactions", sa.Column("withdrawal_details", sa.Text(), nullable=True))
    op.add_column("transactions", sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_tx_reviewed_by", "transactions", "users", ["reviewed_by_id"], ["id"])
    op.add_column("transactions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_transactions_type_status", "transactions", ["tx_type", "status"])

    # investment plans / user investments
    op.add_column("investment_plans", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("user_investments", sa.Column("days_paid", sa.Integer(), nullable=False, server_default="0"))

    # Admin credits used to be recorded as tx_type="deposit" (status completed, no gateway).
    # Re-label them so they no longer pollute the deposit queue/history.
    op.execute(
        "UPDATE transactions SET tx_type = 'admin_credit' "
        "WHERE tx_type = 'deposit' AND gateway_name IS NULL AND status = 'completed'"
    )


def downgrade() -> None:
    op.execute("UPDATE transactions SET tx_type = 'deposit' WHERE tx_type = 'admin_credit'")
    op.drop_column("user_investments", "days_paid")
    op.drop_column("investment_plans", "description")
    op.drop_index("ix_transactions_type_status", table_name="transactions")
    op.drop_column("transactions", "reviewed_at")
    op.drop_constraint("fk_tx_reviewed_by", "transactions", type_="foreignkey")
    op.drop_column("transactions", "reviewed_by_id")
    op.drop_column("transactions", "withdrawal_details")
    op.drop_column("transactions", "fee")
    op.drop_column("transactions", "network")
    op.drop_column("transactions", "asset")
    op.drop_constraint("fk_tx_payment_method", "transactions", type_="foreignkey")
    op.drop_column("transactions", "payment_method_id")
    op.drop_column("users", "kyc_rejection_reason")
    op.drop_column("users", "email_verified")
    op.drop_table("payment_methods")
