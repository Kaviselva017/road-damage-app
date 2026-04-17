"""add geo and indexes

Revision ID: 20260416_0005
Revises: 20260416_0004
Create Date: 2026-04-16 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2

# revision identifiers, used by Alembic.
revision = '20260416_0005'
down_revision = '20260416_0004'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Check if Postgres to safely execute PostGIS spatial indexing
    connection = op.get_bind()
    if connection.engine.dialect.name == 'postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS postgis;')
        
        op.add_column('complaints', sa.Column('location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeogFromText', name='geography'), nullable=True))
        
        # Populate new column from lat/long fields
        op.execute("UPDATE complaints SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
        
        op.create_index('ix_complaints_location', 'complaints', ['location'], postgresql_using='gist')
    
    # Standard b-tree indexes
    op.create_index('ix_complaints_status', 'complaints', ['status'])
    op.create_index('ix_complaints_created_at', 'complaints', ['created_at'])
    op.create_index('ix_complaints_user_id', 'complaints', ['user_id'])

def downgrade() -> None:
    op.drop_index('ix_complaints_user_id', table_name='complaints')
    op.drop_index('ix_complaints_created_at', table_name='complaints')
    op.drop_index('ix_complaints_status', table_name='complaints')
    
    connection = op.get_bind()
    if connection.engine.dialect.name == 'postgresql':
        op.drop_index('ix_complaints_location', table_name='complaints', postgresql_using='gist')
        op.drop_column('complaints', 'location')
        op.execute('DROP EXTENSION IF EXISTS postgis;')
