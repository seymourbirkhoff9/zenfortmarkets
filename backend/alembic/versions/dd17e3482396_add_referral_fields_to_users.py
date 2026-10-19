"""add_referral_fields_to_users

Revision ID: dd17e3482396
Revises: 18a0f45bc68c
Create Date: 2026-10-19 03:53:19.466984

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd17e3482396'
down_revision: Union[str, None] = '18a0f45bc68c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add referral fields to users table
    op.add_column('users', sa.Column('referral_code', sa.String(8), nullable=False, server_default=''))
    op.add_column('users', sa.Column('referred_by_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('users', sa.Column('referral_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('total_referral_earned', sa.Numeric(18, 8), nullable=False, server_default='0.00'))
    
    # Create index on referral_code
    op.create_index('ix_users_referral_code', 'users', ['referral_code'], unique=True)


def downgrade() -> None:
    # Drop referral fields from users table
    op.drop_index('ix_users_referral_code', table_name='users')
    op.drop_column('users', 'total_referral_earned')
    op.drop_column('users', 'referral_count')
    op.drop_column('users', 'referred_by_id')
    op.drop_column('users', 'referral_code')
