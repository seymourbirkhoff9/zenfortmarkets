"""add_manual_deposit_fields_to_transaction

Revision ID: 1c880fcf46aa
Revises: f9d1cc9b0d3c
Create Date: 2026-10-18 14:18:47.271696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c880fcf46aa'
down_revision: Union[str, None] = 'f9d1cc9b0d3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to transactions table
    op.add_column('transactions', sa.Column('gateway_name', sa.String(50), nullable=True))
    op.add_column('transactions', sa.Column('tx_hash', sa.String(255), nullable=True))
    op.add_column('transactions', sa.Column('proof_image_url', sa.String(500), nullable=True))
    op.add_column('transactions', sa.Column('rejection_reason', sa.Text, nullable=True))


def downgrade() -> None:
    # Remove columns from transactions table
    op.drop_column('transactions', 'rejection_reason')
    op.drop_column('transactions', 'proof_image_url')
    op.drop_column('transactions', 'tx_hash')
    op.drop_column('transactions', 'gateway_name')
