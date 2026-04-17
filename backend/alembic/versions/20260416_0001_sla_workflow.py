"""SLA and department workflow

Revision ID: 20260416_0001
Revises: 
Create Date: 2026-04-16 02:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timedelta


# revision identifiers, used by Alembic.
revision = '20260416_0001'
down_revision = None # Usually you'd point to your last revision ID
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create departments table
    op.create_table(
        'departments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('jurisdiction_area', sa.Text(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('max_daily_capacity', sa.Integer(), nullable=True, server_default='50'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # 2. Create sla_config table
    op.create_table(
        'sla_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('resolution_hours', sa.Integer(), nullable=False),
        sa.Column('escalation_after_hours', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('severity')
    )

    # 3. Add columns to complaints
    op.add_column('complaints', sa.Column('department_id', sa.Integer(), nullable=True))
    op.add_column('complaints', sa.Column('sla_deadline', sa.DateTime(), nullable=True))
    op.add_column('complaints', sa.Column('escalated_at', sa.DateTime(), nullable=True))
    op.add_column('complaints', sa.Column('escalation_level', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('complaints', sa.Column('resolved_proof_url', sa.String(), nullable=True))
    
    op.create_foreign_key('fk_complaints_departments', 'complaints', 'departments', ['department_id'], ['id'])

    # 4. Pre-seed departments
    op.execute("INSERT INTO departments (name) VALUES ('Roads'), ('Bridges'), ('Utilities'), ('Emergency')")
    
    # 5. Pre-seed SLA config
    op.execute("INSERT INTO sla_config (severity, resolution_hours, escalation_after_hours) VALUES ('low', 72, 48), ('medium', 48, 24), ('high', 24, 12), ('critical', 4, 2)")


def downgrade():
    op.drop_constraint('fk_complaints_departments', 'complaints', type_='foreignkey')
    op.drop_column('complaints', 'resolved_proof_url')
    op.drop_column('complaints', 'escalation_level')
    op.drop_column('complaints', 'escalated_at')
    op.drop_column('complaints', 'sla_deadline')
    op.drop_column('complaints', 'department_id')
    op.drop_table('sla_config')
    op.drop_table('departments')
