"""admin user flags and audit logs

Revision ID: 0003_admin_users_and_audit_logs
Revises: 0002_invite_codes
Create Date: 2026-11-08 22:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# 迁移的标识
revision: str = '0003_admin_users_and_audit_logs'
down_revision: str | None = '0002_invite_codes'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'is_admin',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'is_active',
            sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False,
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'token_version',
            sa.Integer(),
            server_default='0',
            nullable=False,
        ),
    )
    op.add_column(
        'users',
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'admin_audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('admin_id', sa.UUID(), nullable=True),
        sa.Column('admin_username', sa.String(length=32), nullable=False),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('target_type', sa.String(length=16), nullable=True),
        sa.Column('target_id', sa.UUID(), nullable=True),
        sa.Column(
            'detail',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['admin_id'],
            ['users.id'],
            name=op.f('fk_admin_audit_logs_admin_id_users'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_admin_audit_logs')),
    )
    op.create_index(
        'ix_admin_audit_logs_created_at',
        'admin_audit_logs',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_admin_audit_logs_admin_id'),
        'admin_audit_logs',
        ['admin_id'],
        unique=False,
    )
    op.create_index(
        'ix_admin_audit_logs_action',
        'admin_audit_logs',
        ['action'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_admin_audit_logs_action', table_name='admin_audit_logs')
    op.drop_index(
        op.f('ix_admin_audit_logs_admin_id'), table_name='admin_audit_logs'
    )
    op.drop_index('ix_admin_audit_logs_created_at', table_name='admin_audit_logs')
    op.drop_table('admin_audit_logs')

    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'token_version')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'is_admin')
