"""
Add ai_class and ai_severity columns to complaints

Revision ID: 20260418_0001
Revises: 20260417_0001
Create Date: 2026-04-18 00:00:00.000000

Why these columns?
------------------
DamageResult now returns a typed dataclass with a 4-band severity label
(critical | high | medium | low).  The existing `severity` column stores
the same string but is treated as a user-visible field that officers can
override.  ai_class and ai_severity record the raw AI output before any
officer edits, preserving an immutable inference audit trail.

  ai_class    — normalised class from YOLOv8: pothole | crack |
                surface_damage | multiple.  Mirrors detected_damage_type
                but explicitly typed to the DamageResult.class_name field.

  ai_severity — 4-band label from DamageResult.severity at inference time.
                critical | high | medium | low.

Both columns default to NULL so existing rows are not touched by the
upgrade and the downgrade is a clean drop.

Column existence is checked before adding so this migration is safe to
re-run after a partial failure.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260420_0003"
down_revision = "20260420_0002_refresh_token_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("complaints")}

    with op.batch_alter_table("complaints") as batch_op:
        if "ai_class" not in existing:
            batch_op.add_column(
                sa.Column(
                    "ai_class",
                    sa.String(),
                    nullable=True,
                    comment="Normalised AI class: pothole | crack | surface_damage | multiple",
                )
            )
        if "ai_severity" not in existing:
            batch_op.add_column(
                sa.Column(
                    "ai_severity",
                    sa.String(),
                    nullable=True,
                    comment="4-band AI severity: critical | high | medium | low",
                )
            )


def downgrade() -> None:
    with op.batch_alter_table("complaints") as batch_op:
        # We need to make sure the column exists before dropping, but batch_op handles drops gracefully in most dialects
        # We can just drop them safely
        pass
    
    # Actually executing the drop out of the context (with batch_op on sqlite it might recreate)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("complaints")}
    
    with op.batch_alter_table("complaints") as batch_op:
        if "ai_severity" in existing:
            batch_op.drop_column("ai_severity")
        if "ai_class" in existing:
            batch_op.drop_column("ai_class")
