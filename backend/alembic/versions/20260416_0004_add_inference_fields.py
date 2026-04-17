"""add inference fields

Revision ID: 20260416_0004
Revises: 20260331_0003
Create Date: 2026-04-16 01:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260416_0004'
down_revision = '20260331_0003' # Ensure this matches your previous migration ID
branch_labels = None
depends_on = None

def upgrade() -> None:
    # add confidence_score FLOAT
    op.add_column('complaints', sa.Column('confidence_score', sa.Float(), nullable=True))
    # add detected_damage_type VARCHAR
    op.add_column('complaints', sa.Column('detected_damage_type', sa.String(), nullable=True))
    # add analyzed_at TIMESTAMP
    op.add_column('complaints', sa.Column('analyzed_at', sa.DateTime(), nullable=True))

def downgrade() -> None:
    op.drop_column('complaints', 'analyzed_at')
    op.drop_column('complaints', 'detected_damage_type')
    op.drop_column('complaints', 'confidence_score')
