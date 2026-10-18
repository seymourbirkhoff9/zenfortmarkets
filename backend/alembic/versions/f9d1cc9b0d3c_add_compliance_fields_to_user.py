"""add_compliance_fields_to_user

Revision ID: f9d1cc9b0d3c
Revises: 
Create Date: 2026-10-18 11:14:16.928818

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9d1cc9b0d3c'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create KYCStatus enum type
    kyc_status_enum = sa.Enum('UNVERIFIED', 'PENDING', 'VERIFIED', 'REJECTED', name='kycstatus')
    kyc_status_enum.create(op.get_bind(), checkfirst=True)

    # Add new columns to users table
    op.add_column('users', sa.Column('kyc_status', kyc_status_enum, nullable=False, server_default='UNVERIFIED'))
    op.add_column('users', sa.Column('kyc_document_url', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('is_blocked', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('can_withdraw', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('can_deposit', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    # Remove columns from users table
    op.drop_column('users', 'can_deposit')
    op.drop_column('users', 'can_withdraw')
    op.drop_column('users', 'is_blocked')
    op.drop_column('users', 'kyc_document_url')
    op.drop_column('users', 'kyc_status')

    # Drop KYCStatus enum type
    sa.Enum(name='kycstatus').drop(op.get_bind(), checkfirst=True)
