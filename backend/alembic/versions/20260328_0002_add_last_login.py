"""add last_login to field_officers

Revision ID: 20260328_0002
Revises: 20260325_0001
Create Date: 2026-03-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '20260328_0002'
down_revision = '20260325_0001'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('field_officers') as batch_op:
        batch_op.add_column(sa.Column('last_login', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('field_officers') as batch_op:
        batch_op.drop_column('last_login')