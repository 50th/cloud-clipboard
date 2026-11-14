"""users.share_limit

Revision ID: 0008_user_share_limit
Revises: 0007_share_access_logs
Create Date: 2026-11-14 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# 迁移的标识
revision: str = '0008_user_share_limit'
down_revision: str | None = '0007_share_access_logs'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL = 跟随 share_settings.user_share_limit
    op.add_column(
        'users',
        sa.Column('share_limit', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'share_limit')
