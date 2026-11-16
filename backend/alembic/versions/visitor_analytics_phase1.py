"""visitor_analytics_phase1

Visitor analytics and traffic tracking tables.

Revision ID: visitor_analytics_phase1
Revises: fx_multi_currency_phase1
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'visitor_analytics_phase1'
down_revision: Union[str, None] = 'fx_multi_currency_phase1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'site_visitors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('visitor_id', sa.String(64), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ip_address', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('current_path', sa.String(255), nullable=False),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('device_type', sa.String(50), nullable=True),
        sa.Column('referrer', sa.Text(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('page_views', sa.Integer(), server_default='1', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_site_visitors_visitor_id', 'site_visitors', ['visitor_id'], unique=True)
    op.create_index('ix_site_visitors_user_id', 'site_visitors', ['user_id'])
    op.create_index('ix_site_visitors_last_seen_at', 'site_visitors', ['last_seen_at'])

    op.create_table(
        'visitor_page_views',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('visitor_id', sa.String(64), nullable=False),
        sa.Column('path', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_visitor_page_views_visitor_id', 'visitor_page_views', ['visitor_id'])
    op.create_index('ix_visitor_page_views_created_at', 'visitor_page_views', ['created_at'])


def downgrade() -> None:
    op.drop_table('visitor_page_views')
    op.drop_table('site_visitors')

