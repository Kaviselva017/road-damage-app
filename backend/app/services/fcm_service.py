import logging
import os
from typing import Any

logger = logging.getLogger("roadwatch")

_fcm_available = False

try:
    import firebase_admin
    from firebase_admin import credentials, messaging

    _fcm_available = True

    # Prefer JSON path if provided
    path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if path and os.path.exists(path):
        cred = credentials.Certificate(path)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        logger.info("FCM: Firebase Admin initialized successfully from path.")
    elif os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON"):
        import base64
        import json

        service_account_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        service_account_json = base64.b64decode(service_account_b64).decode("utf-8")
        service_account_info = json.loads(service_account_json)
        cred = credentials.Certificate(service_account_info)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        logger.info("FCM: Firebase Admin initialized successfully from JSON string.")
    else:
        logger.warning("FCM: No Firebase credentials found. Push notifications disabled.")
except ImportError:
    _fcm_available = False
except Exception as e:
    logger.error(f"FCM: Initialization failed: {e}")
    _fcm_available = False


async def send_push(fcm_token: str, title: str, body: str, data: dict[str, Any] = None) -> bool:
    if not _fcm_available or not fcm_token:
        return False

    if data is None:
        data = {}
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
        messaging.send(message)
        logger.info(f"FCM: Sent '{title}' to {fcm_token[:20]}...")
        return True
    except Exception as e:
        logger.error(f"FCM: Failed to send message: {e}")
        return False


async def send_push_bulk(tokens: list, title: str, body: str, data: dict[str, Any] = None) -> bool:
    if not _fcm_available or not tokens:
        return False

    tokens = tokens[:500]
    if data is None:
        data = {}
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
        return response.success_count > 0
    except Exception as e:
        logger.error(f"FCM Bulk: Failed to send multicast message: {e}")
        return False


async def send_status_update(user_fcm_token: str, complaint_id: str, new_status: str) -> bool:
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
    return await send_push(fcm_token=user_fcm_token, title="Budget Allocated", body=f"Rs. {amount:,.0f} has been allocated for your report {complaint_id}.", data={"complaint_id": complaint_id, "screen": "complaint_detail", "type": "funded"})


async def send_emergency_alert(fcm_token: str, complaint_id: str) -> bool:
    return await send_push(fcm_token=fcm_token, title="🚨 Severe Road Hazard", body="Severe road damage reported nearby. Drive carefully.", data={"complaint_id": complaint_id, "screen": "map", "priority": "high", "type": "emergency"})
