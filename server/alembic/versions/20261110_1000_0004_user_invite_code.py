"""add users.invite_code_id

Revision ID: 0004_user_invite_code
Revises: 0003_admin_users_and_audit_logs
Create Date: 2026-11-10 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# 迁移的标识
revision: str = '0004_user_invite_code'
down_revision: str | None = '0003_admin_users_and_audit_logs'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('invite_code_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f('fk_users_invite_code_id_invite_codes'),
        'users',
        'invite_codes',
        ['invite_code_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        op.f('ix_users_invite_code_id'),
        'users',
        ['invite_code_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_users_invite_code_id'), table_name='users')
    op.drop_constraint(
        op.f('fk_users_invite_code_id_invite_codes'),
        'users',
        type_='foreignkey',
    )
    op.drop_column('users', 'invite_code_id')
