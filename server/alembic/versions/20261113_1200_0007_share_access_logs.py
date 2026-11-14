"""share access logs

Revision ID: 0007_share_access_logs
Revises: 0006_share_settings
Create Date: 2026-11-13 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# 迁移的标识
revision: str = '0007_share_access_logs'
down_revision: str | None = '0006_share_settings'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'clipboard_share_access_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('share_id', sa.UUID(), nullable=False),
        sa.Column(
            'accessed_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('result', sa.String(length=16), nullable=False),
        sa.Column(
            'ip',
            postgresql.INET(),
            nullable=True,
        ),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ['share_id'],
            ['clipboard_shares.id'],
            name=op.f('fk_clipboard_share_access_logs_share_id_clipboard_shares'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint(
            'id', name=op.f('pk_clipboard_share_access_logs')
        ),
    )
    op.create_index(
        op.f('ix_clipboard_share_access_logs_share_id'),
        'clipboard_share_access_logs',
        ['share_id'],
        unique=False,
    )
    op.create_index(
        'ix_share_access_logs_share_accessed',
        'clipboard_share_access_logs',
        ['share_id', 'accessed_at'],
        unique=False,
    )
    op.create_index(
        'ix_share_access_logs_result_accessed',
        'clipboard_share_access_logs',
        ['result', 'accessed_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_share_access_logs_result_accessed',
        table_name='clipboard_share_access_logs',
    )
    op.drop_index(
        'ix_share_access_logs_share_accessed',
        table_name='clipboard_share_access_logs',
    )
    op.drop_index(
        op.f('ix_clipboard_share_access_logs_share_id'),
        table_name='clipboard_share_access_logs',
    )
    op.drop_table('clipboard_share_access_logs')
