import logging
import os
from typing import Any

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger("roadwatch")

# Global flag to check if FCM is configured
_fcm_available = False

try:
    # Prefer JSON path if provided
    path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if path and os.path.exists(path):
        cred = credentials.Certificate(path)
        # Check if already initialized to avoid "app already exists" error
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        _fcm_available = True
        logger.info("FCM: Firebase Admin initialized successfully from path.")
    elif os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON"):
        # Fallback for base64 encoded JSON (useful for Render/CI)
        import base64
        import json

        service_account_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        service_account_json = base64.b64decode(service_account_b64).decode("utf-8")
        service_account_info = json.loads(service_account_json)
        cred = credentials.Certificate(service_account_info)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        _fcm_available = True
        logger.info("FCM: Firebase Admin initialized successfully from JSON string.")
    else:
        logger.warning("FCM: No Firebase credentials found. Push notifications disabled.")
except Exception as e:
    logger.error(f"FCM: Initialization failed: {e}")
    _fcm_available = False


async def send_push(fcm_token: str, title: str, body: str, data: dict[str, Any] = None) -> bool:
    """
    Sends a push notification to a specific FCM token.
    Catches UnregisteredError and InvalidArgumentError.
    """
    if not _fcm_available or not fcm_token:
        # Prevent noise in logs if FCM is intentionally disabled
        return False

    # FCM requires all values in data to be strings
    data_str = {str(k): str(v) for k, v in data.items()}

    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data_str,
        token=fcm_token,
    )

    try:
        # messaging.send is a blocking call, wait for completion
        messaging.send(message)
        logger.info(f"FCM: Sent '{title}' to {fcm_token[:20]}...")
        return True
    except firebase_admin.exceptions.InvalidArgumentError as e:
        logger.warning(f"FCM: Stale token: {fcm_token[:20]}... - {e}")
        return False
    except firebase_admin.messaging.UnregisteredError as e:
        logger.warning(f"FCM: Unregistered token: {fcm_token[:20]}... - {e}")
        # Optionally, could clean up token from DB here
        return False
    except Exception as e:
        logger.error(f"FCM: Failed to send message: {e}")
        return False


async def send_push_bulk(tokens: list, title: str, body: str, data: dict[str, Any] = None) -> tuple[int, int]:
    """
    Use messaging.MulticastMessage for up to 500 tokens
    Returns (success_count, failure_count)
    """
    if not _fcm_available or not tokens:
        return (0, 0)

    # max 500 per MulticastMessage
    tokens = tokens[:500]
    data_str = {str(k): str(v) for k, v in data.items()}

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data_str,
        tokens=tokens,
    )

    try:
        response = messaging.send_each_for_multicast(message)
        logger.info(f"FCM Bulk: success_count={response.success_count}, failure_count={response.failure_count}")
        return (response.success_count, response.failure_count)
    except Exception as e:
        logger.error(f"FCM Bulk: Failed to send multicast message: {e}")
        return (0, 0)


async def send_status_update(user_fcm_token: str, complaint_id: str, new_status: str) -> bool:
    """
    Sends a push notification for a complaint status update.
    """
    STATUS_MESSAGES = {
        "analyzed": "Your road damage report has been reviewed by AI.",
        "assigned": "A field officer has been assigned to your report.",
        "in_progress": "Repair work has started on the reported damage.",
        "completed": "The road damage you reported has been fixed! Thank you.",
        "rejected": "Your report has been reviewed and closed by the administration.",
        "escalated": "Your report has been escalated for urgent attention.",
    }

    body = STATUS_MESSAGES.get(new_status, f"The status of your report {complaint_id} changed to {new_status}.")

    return await send_push(fcm_token=user_fcm_token, title="RoadWatch Update", body=body, data={"complaint_id": complaint_id, "screen": "complaint_detail", "status": new_status, "type": "status_update"})


async def send_fund_allocated_notification(user_fcm_token: str, complaint_id: str, amount: float) -> bool:
    """Notify user that budget has been allocated for their report."""
    return await send_push(fcm_token=user_fcm_token, title="Budget Allocated", body=f"Rs. {amount:,.0f} has been allocated for your report {complaint_id}.", data={"complaint_id": complaint_id, "screen": "complaint_detail", "type": "funded"})


async def send_emergency_alert(fcm_token: str, complaint_id: str):
    """Notify nearby users (if token known) about a severe hazard."""
    return await send_push(fcm_token=fcm_token, title="🚨 Severe Road Hazard", body="Severe road damage reported nearby. Drive carefully.", data={"complaint_id": complaint_id, "screen": "map", "priority": "high", "type": "emergency"}, priority="high")
