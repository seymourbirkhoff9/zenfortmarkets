"""fx_multi_currency_phase1

Multi-currency Phase 1: FX rates table and input currency tracking.

Revision ID: fx_multi_currency_phase1
Revises: b1edabefbc1e
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'fx_multi_currency_phase1'
down_revision: Union[str, None] = 'b1edabefbc1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create fx_rates table
    op.create_table(
        'fx_rates',
        sa.Column('currency', sa.String(10), primary_key=True, nullable=False),
        sa.Column('rate_per_usd', sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column('override_rate', sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('source', sa.String(50), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Add input currency tracking to transactions
    op.add_column('transactions', sa.Column('input_amount', sa.Numeric(precision=20, scale=8), nullable=True))
    op.add_column('transactions', sa.Column('input_currency', sa.String(10), nullable=True))
    op.add_column('transactions', sa.Column('fx_rate', sa.Numeric(precision=20, scale=10), nullable=True))

    # Add display currency preference to users
    op.add_column('users', sa.Column('display_currency', sa.String(10), nullable=True))


def downgrade() -> None:
    # Remove columns from transactions
    op.drop_column('transactions', 'fx_rate')
    op.drop_column('transactions', 'input_currency')
    op.drop_column('transactions', 'input_amount')

    # Remove column from users
    op.drop_column('users', 'display_currency')

    # Drop fx_rates table
    op.drop_table('fx_rates')
