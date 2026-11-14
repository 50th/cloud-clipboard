"""clipboard shares

Revision ID: 0005_clipboard_shares
Revises: 0004_user_invite_code
Create Date: 2026-11-12 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# 迁移的标识
revision: str = '0005_clipboard_shares'
down_revision: str | None = '0004_user_invite_code'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'clipboard_shares',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column(
            'mode',
            sa.String(length=16),
            server_default='snapshot',
            nullable=False,
        ),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column(
            'content_type',
            sa.String(length=16),
            server_default='text',
            nullable=False,
        ),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('max_views', sa.Integer(), nullable=True),
        sa.Column(
            'view_count',
            sa.Integer(),
            server_default='0',
            nullable=False,
        ),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('last_viewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['item_id'],
            ['clipboard_items.id'],
            name=op.f('fk_clipboard_shares_item_id_clipboard_items'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            name=op.f('fk_clipboard_shares_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_clipboard_shares')),
        sa.UniqueConstraint('token', name=op.f('uq_clipboard_shares_token')),
    )
    op.create_index(
        op.f('ix_clipboard_shares_user_id'),
        'clipboard_shares',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_clipboard_shares_item_id'),
        'clipboard_shares',
        ['item_id'],
        unique=False,
    )
    op.create_index(
        'ix_clipboard_shares_user_created',
        'clipboard_shares',
        ['user_id', 'created_at'],
        unique=False,
    )
    op.create_index(
        'ix_clipboard_shares_expires_at',
        'clipboard_shares',
        ['expires_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_clipboard_shares_expires_at', table_name='clipboard_shares')
    op.drop_index('ix_clipboard_shares_user_created', table_name='clipboard_shares')
    op.drop_index(
        op.f('ix_clipboard_shares_item_id'), table_name='clipboard_shares'
    )
    op.drop_index(
        op.f('ix_clipboard_shares_user_id'), table_name='clipboard_shares'
    )
    op.drop_table('clipboard_shares')
