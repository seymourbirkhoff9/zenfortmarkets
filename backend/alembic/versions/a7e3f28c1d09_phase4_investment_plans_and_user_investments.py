"""phase4_investment_plans_and_user_investments

Revision ID: a7e3f28c1d09
Revises: d5fc16e17b16
Create Date: 2026-10-19 01:05:00.000000

Drops the legacy `investments` table and creates the Phase 4
`investment_plans` and `user_investments` tables.
"""
from typing import Sequence, Union
from decimal import Decimal

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a7e3f28c1d09'
down_revision: Union[str, None] = 'd5fc16e17b16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Drop legacy investments table (placeholder from Phase 1) ──────────
    op.drop_table('investments')

    # ── Create investment_plans ───────────────────────────────────────────
    op.create_table(
        'investment_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('min_amount', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('max_amount', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('daily_roi_percent', sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_investment_plans_name', 'investment_plans', ['name'], unique=True)

    # ── Create user_investments ───────────────────────────────────────────
    op.create_table(
        'user_investments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'plan_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('investment_plans.id'),
            nullable=False,
        ),
        sa.Column('amount_invested', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('daily_roi_percent', sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column(
            'total_earned',
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            server_default='0.0',
        ),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('maturity_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_user_investments_user_id', 'user_investments', ['user_id'])
    op.create_index('ix_user_investments_plan_id', 'user_investments', ['plan_id'])
    op.create_index('ix_user_investments_status', 'user_investments', ['status'])


def downgrade() -> None:
    # Drop Phase 4 tables
    op.drop_index('ix_user_investments_status', table_name='user_investments')
    op.drop_index('ix_user_investments_plan_id', table_name='user_investments')
    op.drop_index('ix_user_investments_user_id', table_name='user_investments')
    op.drop_table('user_investments')

    op.drop_index('ix_investment_plans_name', table_name='investment_plans')
    op.drop_table('investment_plans')

    # Recreate the legacy investments table
    op.create_table(
        'investments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('plan_name', sa.String(100), nullable=False),
        sa.Column('amount', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('currency', sa.String(10), nullable=False, server_default='USD'),
        sa.Column('roi_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('matures_at', sa.DateTime(timezone=True), nullable=True),
    )
