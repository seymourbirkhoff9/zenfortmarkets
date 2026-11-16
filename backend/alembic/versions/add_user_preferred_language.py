"""add_user_preferred_language

Add preferred_language column to users table.

Revision ID: add_user_preferred_language
Revises: visitor_analytics_phase1
Create Date: 2026-11-16
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'add_user_preferred_language'
down_revision: Union[str, None] = 'visitor_analytics_phase1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('preferred_language', sa.String(length=10), nullable=False, server_default='en')
    )


def downgrade() -> None:
    op.drop_column('users', 'preferred_language')

