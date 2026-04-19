"""refresh token family table

Revision ID: 20260420_0002_refresh_token_table
Revises: 20260420_0001_google_auth
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260420_0002_refresh_token_table'
down_revision = '20260420_0001_google_auth'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refresh_tokens",
        sa.Column("id",                 sa.Integer,     primary_key=True),
        sa.Column("jti",                sa.String(36),  unique=True, nullable=False),
        sa.Column("user_id",            sa.Integer,     sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash",         sa.String(256), nullable=False),
        sa.Column("family_id",          sa.String(36),  nullable=False),
        sa.Column("device_fingerprint", sa.String(512), nullable=True),
        sa.Column("created_at",         sa.DateTime,    nullable=False),
        sa.Column("expires_at",         sa.DateTime,    nullable=False),
        sa.Column("used_at",            sa.DateTime,    nullable=True),
        sa.Column("revoked",            sa.Boolean,     default=False, nullable=False),
    )
    op.create_index("idx_rt_user_id",   "refresh_tokens", ["user_id"])
    op.create_index("idx_rt_family_id", "refresh_tokens", ["family_id"])
    op.create_index("idx_rt_jti",       "refresh_tokens", ["jti"])

    # One-time revocation tokens for "sign out all devices" email link
    op.create_table(
        "revocation_tokens",
        sa.Column("id",         sa.Integer,    primary_key=True),
        sa.Column("token",      sa.String(64), unique=True, nullable=False),
        sa.Column("user_id",    sa.Integer,    sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("used",       sa.Boolean,    default=False, nullable=False),
        sa.Column("expires_at", sa.DateTime,   nullable=False),
        sa.Column("created_at", sa.DateTime,   nullable=False),
    )

def downgrade():
    op.drop_table("revocation_tokens")
    op.drop_table("refresh_tokens")
