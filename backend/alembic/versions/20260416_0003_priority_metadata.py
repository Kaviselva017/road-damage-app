"""Add priority metadata columns

Revision ID: 20260416_0003
Revises: 20260416_0002
Create Date: 2026-04-16 02:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260416_0003'
down_revision = '20260416_0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('complaints', sa.Column('urgency_label', sa.String(), nullable=True))
    op.add_column('complaints', sa.Column('priority_breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('complaints', 'priority_breakdown')
    op.drop_column('complaints', 'urgency_label')
