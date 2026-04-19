"""google_auth_migration

Revision ID: 20260420_0001_google_auth
Revises: 907cf5678d40
Create Date: 2026-04-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260420_0001_google_auth'
down_revision: Union[str, None] = '907cf5678d40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy.engine.reflection import Inspector
    inspector = Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]

    if "google_sub" not in columns:
        op.add_column("users", sa.Column("google_sub", sa.String(128), nullable=True))
    if "picture_url" not in columns:
        op.add_column("users", sa.Column("picture_url", sa.String(512), nullable=True))
    if "phone_number" not in columns:
        op.add_column("users", sa.Column("phone_number", sa.String(20), nullable=True))
    if "phone_verified_at" not in columns:
        op.add_column("users", sa.Column("phone_verified_at", sa.DateTime, nullable=True))
    if "refresh_token_hash" not in columns:
        op.add_column("users", sa.Column("refresh_token_hash", sa.String(256), nullable=True))
    if "refresh_token_expires_at" not in columns:
        op.add_column("users", sa.Column("refresh_token_expires_at", sa.DateTime, nullable=True))
    if "last_login_at" not in columns:
        op.add_column("users", sa.Column("last_login_at", sa.DateTime, nullable=True))
    if "is_officer" not in columns:
        op.add_column("users", sa.Column("is_officer", sa.Boolean, server_default="0"))

    # Indexes & constraints (ignore errors on sqlite)
    try:
        op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)
    except Exception:
        pass
    try:
        op.create_index("ix_users_phone_number", "users", ["phone_number"], unique=True)
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_index("ix_users_phone_number", table_name="users")
    except Exception:
        pass
    try:
        op.drop_index("ix_users_google_sub", table_name="users")
    except Exception:
        pass
    for col in ("is_officer", "last_login_at", "refresh_token_expires_at",
                "refresh_token_hash", "phone_verified_at", "phone_number",
                "picture_url", "google_sub"):
        try:
            op.drop_column("users", col)
        except Exception:
            pass
