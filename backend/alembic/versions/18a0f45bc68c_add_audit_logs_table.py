"""add_audit_logs_table

Revision ID: 18a0f45bc68c
Revises: 43a107d8a66f
Create Date: 2026-10-19 03:33:34.460109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18a0f45bc68c'
down_revision: Union[str, None] = '43a107d8a66f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('admin_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('target_user_id', sa.UUID(as_uuid=True), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )


def downgrade() -> None:
    # Drop audit_logs table
    op.drop_table('audit_logs')
