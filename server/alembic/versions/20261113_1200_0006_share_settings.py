"""share settings

Revision ID: 0006_share_settings
Revises: 0005_clipboard_shares
Create Date: 2026-11-13 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# 迁移的标识
revision: str = '0006_share_settings'
down_revision: str | None = '0005_clipboard_shares'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'share_settings',
        sa.Column('id', sa.SmallInteger(), nullable=False),
        sa.Column(
            'user_share_limit',
            sa.Integer(),
            server_default='50',
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.CheckConstraint(
            'id = 1', name=op.f('ck_share_settings_single_row')
        ),
        sa.ForeignKeyConstraint(
            ['updated_by'],
            ['users.id'],
            name=op.f('fk_share_settings_updated_by_users'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_share_settings')),
    )
    # 单行配置：默认限额 50。代码读取时若行缺失也回退 50。
    op.execute(
        "INSERT INTO share_settings (id, user_share_limit) VALUES (1, 50)"
    )


def downgrade() -> None:
    op.drop_table('share_settings')
