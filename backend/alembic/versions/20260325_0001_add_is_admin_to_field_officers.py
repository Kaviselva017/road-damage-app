"""Add explicit is_admin flag to field officers.

Revision ID: 20260325_0001
Revises:
Create Date: 2026-03-25 23:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260325_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_users_table(inspector) -> None:
    if "users" in inspector.get_table_names():
        return

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("points", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def _create_field_officers_table(inspector) -> None:
    if "field_officers" in inspector.get_table_names():
        return

    op.create_table(
        "field_officers",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("zone", sa.String(length=100), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("email", name="uq_field_officers_email"),
    )
    op.create_index("ix_field_officers_id", "field_officers", ["id"], unique=False)
    op.create_index("ix_field_officers_email", "field_officers", ["email"], unique=True)


def _create_complaints_table(inspector) -> None:
    if "complaints" in inspector.get_table_names():
        return

    severity_enum = sa.Enum("LOW", "MEDIUM", "HIGH", name="severitylevel")
    status_enum = sa.Enum("PENDING", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "REJECTED", name="complaintstatus")
    damage_enum = sa.Enum("POTHOLE", "CRACK", "SURFACE_DAMAGE", "MULTIPLE", name="damagetype")

    op.create_table(
        "complaints",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("complaint_id", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("officer_id", sa.Integer(), sa.ForeignKey("field_officers.id"), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("area_type", sa.String(length=50), nullable=True, server_default="unknown"),
        sa.Column("nearby_places", sa.Text(), nullable=True),
        sa.Column("damage_type", damage_enum, nullable=False),
        sa.Column("severity", severity_enum, nullable=False),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("image_thumbnail_url", sa.String(length=500), nullable=True),
        sa.Column("image_hash", sa.String(length=64), nullable=True),
        sa.Column("status", status_enum, nullable=True, server_default="PENDING"),
        sa.Column("officer_notes", sa.Text(), nullable=True),
        sa.Column("priority_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("damage_size_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("traffic_density_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("accident_risk_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("area_criticality_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("rainfall_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("rainfall_mm", sa.Float(), nullable=True),
        sa.Column("traffic_volume", sa.String(length=50), nullable=True),
        sa.Column("road_age_years", sa.Integer(), nullable=True),
        sa.Column("weather_condition", sa.String(length=100), nullable=True),
        sa.Column("allocated_fund", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("fund_note", sa.Text(), nullable=True),
        sa.Column("fund_allocated_at", sa.DateTime(), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("duplicate_of", sa.String(length=20), nullable=True),
        sa.Column("report_count", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("is_verified", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("fake_report_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("complaint_id", name="uq_complaints_complaint_id"),
    )
    op.create_index("ix_complaints_id", "complaints", ["id"], unique=False)
    op.create_index("ix_complaints_complaint_id", "complaints", ["complaint_id"], unique=True)


def _create_messages_table(inspector) -> None:
    if "messages" in inspector.get_table_names():
        return

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("complaint_id", sa.String(length=20), sa.ForeignKey("complaints.complaint_id"), nullable=True),
        sa.Column("sender_role", sa.String(length=20), nullable=True),
        sa.Column("sender_name", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_messages_id", "messages", ["id"], unique=False)


def _create_login_logs_table(inspector) -> None:
    if "login_logs" in inspector.get_table_names():
        return

    op.create_table(
        "login_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("logged_in_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("logout_at", sa.DateTime(), nullable=True),
        sa.Column("session_duration_mins", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="success"),
    )
    op.create_index("ix_login_logs_id", "login_logs", ["id"], unique=False)


def _create_complaint_officers_table(inspector) -> None:
    if "complaint_officers" in inspector.get_table_names():
        return

    op.create_table(
        "complaint_officers",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("complaint_id", sa.String(length=20), sa.ForeignKey("complaints.complaint_id"), nullable=True),
        sa.Column("officer_id", sa.Integer(), sa.ForeignKey("field_officers.id"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("role", sa.String(length=50), nullable=True, server_default="field"),
    )
    op.create_index("ix_complaint_officers_id", "complaint_officers", ["id"], unique=False)


def _create_notifications_table(inspector) -> None:
    if "notifications" in inspector.get_table_names():
        return

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("complaint_id", sa.String(length=20), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"], unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _create_users_table(inspector)
    inspector = sa.inspect(bind)
    _create_field_officers_table(inspector)
    inspector = sa.inspect(bind)
    _create_complaints_table(inspector)
    inspector = sa.inspect(bind)
    _create_messages_table(inspector)
    _create_login_logs_table(inspector)
    _create_complaint_officers_table(inspector)
    _create_notifications_table(inspector)
    inspector = sa.inspect(bind)

    if "field_officers" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("field_officers")}
    if "is_admin" in columns:
        return

    with op.batch_alter_table("field_officers") as batch_op:
        batch_op.add_column(sa.Column("is_admin", sa.Boolean(), nullable=True, server_default=sa.false()))

    op.execute("UPDATE field_officers SET is_admin = 1 WHERE zone = 'All Zones'")
    op.execute("UPDATE field_officers SET is_admin = 0 WHERE is_admin IS NULL")

    with op.batch_alter_table("field_officers") as batch_op:
        batch_op.alter_column("is_admin", existing_type=sa.Boolean(), nullable=False, server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "field_officers" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("field_officers")}
    if "is_admin" not in columns:
        return

    with op.batch_alter_table("field_officers") as batch_op:
        batch_op.drop_column("is_admin")
