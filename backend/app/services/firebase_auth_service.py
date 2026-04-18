import base64
import json
import logging
import os

import firebase_admin
from fastapi import HTTPException, status
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

logger = logging.getLogger(__name__)

_firebase_app = None


def init_firebase():
    global _firebase_app
    if _firebase_app:
        return

    svc_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    try:
        if svc_json:
            cert_dict = json.loads(base64.b64decode(svc_json))
            cred = credentials.Certificate(cert_dict)
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized with service account from env.")
        else:
            # Local development fallback to file or ADC
            cert_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
            if cert_path and os.path.exists(cert_path):
                cred = credentials.Certificate(cert_path)
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info(f"Firebase initialized with service account from file: {cert_path}")
            else:
                _firebase_app = firebase_admin.initialize_app()
                logger.info("Firebase initialized with Application Default Credentials.")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")


def verify_firebase_token(id_token: str) -> dict:
    """
    Verifies Firebase ID token. Returns decoded token dict:
    { "uid": str, "email": str, "email_verified": bool,
      "phone_number": str (if OTP login), ... }
    Raises HTTP 401 on invalid/expired token.
    """
    try:
        # check_revoked=True provides extra security but adds latency (network call to Firebase)  # noqa: E501
        return firebase_auth.verify_id_token(id_token, check_revoked=True)
    except firebase_auth.RevokedIdTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked — please log in again",
        ) from e
    except firebase_auth.ExpiredIdTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from e
    except Exception as e:
        logger.warning(f"Firebase token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from e
