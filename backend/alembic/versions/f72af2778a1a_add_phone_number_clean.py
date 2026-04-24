"""add phone_number clean

Revision ID: f72af2778a1a
Revises: 20260420_0003
Create Date: 2026-04-22 21:14:19.510267
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = 'f72af2778a1a'
down_revision: Union[str, None] = '20260420_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- field_officers: rename phone -> phone_number ---
    with op.batch_alter_table('field_officers') as batch_op:
        batch_op.alter_column('phone', new_column_name='phone_number')

    # --- users: rename phone -> phone_number, add missing columns ---
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('phone', new_column_name='phone_number')
        batch_op.add_column(sa.Column('google_sub', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('picture_url', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('phone_verified_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(), nullable=True))
        batch_op.alter_column('hashed_password',
                              existing_type=sa.VARCHAR(),
                              nullable=True)
        batch_op.create_index('ix_users_google_sub', ['google_sub'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_index('ix_users_google_sub')
        batch_op.alter_column('hashed_password',
                              existing_type=sa.VARCHAR(),
                              nullable=False)
        batch_op.drop_column('last_login_at')
        batch_op.drop_column('phone_verified_at')
        batch_op.drop_column('picture_url')
        batch_op.drop_column('google_sub')
        batch_op.alter_column('phone_number', new_column_name='phone')

    with op.batch_alter_table('field_officers') as batch_op:
        batch_op.alter_column('phone_number', new_column_name='phone')
