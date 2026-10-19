"""add_withdrawal_fields_to_transaction

Revision ID: d5fc16e17b16
Revises: 1c880fcf46aa
Create Date: 2026-10-18 18:18:41.052584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5fc16e17b16'
down_revision: Union[str, None] = '1c880fcf46aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add withdrawal-specific columns to transactions table
    op.add_column('transactions', sa.Column('withdrawal_address', sa.String(255), nullable=True))
    op.add_column('transactions', sa.Column('payout_tx_hash', sa.String(255), nullable=True))


def downgrade() -> None:
    # Remove withdrawal columns from transactions table
    op.drop_column('transactions', 'payout_tx_hash')
    op.drop_column('transactions', 'withdrawal_address')
