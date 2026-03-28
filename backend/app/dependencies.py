"""
app/dependencies.py — re-exports auth helpers for import convenience
"""
from app.services.auth_service import (
    get_current_user,
    get_current_officer,
    get_current_admin,
)

__all__ = ["get_current_user", "get_current_officer", "get_current_admin"]