"""
RoadWatch — Google Auth Service
Verifies Google ID tokens and returns a GoogleUser dataclass.
Lazy-initialised so tests can import without GOOGLE_CLIENT_ID being set.
"""

from dataclasses import dataclass
from fastapi import HTTPException
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class GoogleUser:
    sub: str
    email: str
    name: str
    picture: str
    email_verified: bool


class GoogleAuthService:
    def __init__(self):
        self._client_id: str | None = None

    @property
    def client_id(self) -> str:
        if self._client_id is None:
            self._client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        return self._client_id

    def verify_id_token(self, token: str) -> GoogleUser:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        if not self.client_id:
            raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured")

        try:
            info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                self.client_id,
            )
        except ValueError as e:
            logger.warning("Google token verification failed: %s", e)
            raise HTTPException(status_code=401, detail="Invalid Google token")

        if not info.get("email_verified", False):
            raise HTTPException(status_code=403, detail="Email not verified by Google")

        return GoogleUser(
            sub=info["sub"],
            email=info["email"],
            name=info.get("name", ""),
            picture=info.get("picture", ""),
            email_verified=info["email_verified"],
        )


google_auth_service = GoogleAuthService()
