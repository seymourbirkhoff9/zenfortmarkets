"""add_broadcast_logs_table

Revision ID: 43a107d8a66f
Revises: 5ab915eef167
Create Date: 2026-10-19 03:15:54.816717

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43a107d8a66f'
down_revision: Union[str, None] = '5ab915eef167'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create broadcast_logs table
    op.create_table(
        'broadcast_logs',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('admin_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('target_filter', sa.String(50), nullable=False, server_default='all'),
        sa.Column('recipient_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )


def downgrade() -> None:
    # Drop broadcast_logs table
    op.drop_table('broadcast_logs')
