"""initial

Revision ID: 0001
Revises: 
Create Date: 2026-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    op.create_table(
        'field_officers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('zone', sa.String(), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    op.create_table(
        'complaints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('damage_type', sa.String(), nullable=True),
        sa.Column('severity', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('area_type', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, default='pending'),
        sa.Column('priority_score', sa.Float(), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True),
        sa.Column('allocated_budget', sa.Float(), nullable=True),
        sa.Column('image_path', sa.String(), nullable=True),
        sa.Column('ai_processed', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'complaint_officers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=True),
        sa.Column('officer_id', sa.Integer(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id']),
        sa.ForeignKeyConstraint(['officer_id'], ['field_officers.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=True),
        sa.Column('sender_type', sa.String(), nullable=True),
        sa.Column('sender_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('message', sa.String(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'login_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('officer_id', sa.Integer(), nullable=True),
        sa.Column('login_at', sa.DateTime(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['officer_id'], ['field_officers.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('login_logs')
    op.drop_table('notifications')
    op.drop_table('messages')
    op.drop_table('complaint_officers')
    op.drop_table('complaints')
    op.drop_table('field_officers')
    op.drop_table('users')