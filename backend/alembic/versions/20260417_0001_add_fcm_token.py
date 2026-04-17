"""add fcm_token

Revision ID: 20260417_0001
Revises: 20260416_0005
Create Date: 2026-04-17 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260417_0001'
down_revision = '20260416_0005'
branch_labels = None
depends_on = None

def upgrade():
    # Check if column already exists to avoid errors if partially applied
    conn = op.get_bind()
    columns = sa.inspect(conn).get_columns('users')
    if not any(c['name'] == 'fcm_token' for c in columns):
        op.add_column('users', sa.Column('fcm_token', sa.String(), nullable=True))

def downgrade():
    op.drop_column('users', 'fcm_token')
