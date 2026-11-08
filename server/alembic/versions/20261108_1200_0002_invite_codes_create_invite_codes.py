"""create invite_codes

Revision ID: 0002_invite_codes
Revises: 0001_initial
Create Date: 2026-11-08 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# 迁移的标识
revision: str = '0002_invite_codes'
down_revision: str | None = '0001_initial'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'invite_codes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('code_hint', sa.String(length=8), nullable=False),
        sa.Column('label', sa.String(length=64), nullable=True),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('used_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_invite_codes')),
    )
    op.create_index(
        op.f('ix_invite_codes_code_hash'), 'invite_codes', ['code_hash'], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_invite_codes_code_hash'), table_name='invite_codes')
    op.drop_table('invite_codes')
