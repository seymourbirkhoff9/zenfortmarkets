"""add_bank_transfer_payment_method

Revision ID: b1edabefbc1e
Revises: d4e6a8c0b3f5
Create Date: 2026-10-21 12:48:54.861806

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1edabefbc1e'
down_revision: Union[str, None] = 'd4e6a8c0b3f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'payment_methods',
        sa.Column('method_type', sa.String(length=10), nullable=False, server_default='crypto'),
    )
    op.add_column(
        'payment_methods',
        sa.Column('bank_details', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('payment_methods', 'bank_details')
    op.drop_column('payment_methods', 'method_type')