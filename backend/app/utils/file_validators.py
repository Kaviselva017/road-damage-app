import io
import os

import magic
from fastapi import UploadFile
from fastapi.responses import JSONResponse
from PIL import Image


async def validate_image(image: UploadFile) -> tuple[bytes | None, JSONResponse | None]:
    """
    Validates an uploaded image for size, MIME type, and internal integrity.
    Returns (image_bytes, None) on success.
    Returns (None, JSONResponse) on validation failure.
    """
    max_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
    max_bytes = max_mb * 1024 * 1024

    image_bytes = await image.read()

    # 1. Size Validation
    if len(image_bytes) > max_bytes:
        return None, JSONResponse(status_code=413, content={"detail": f"File exceeds maximum allowed size of {max_mb}MB", "code": "INVALID_FILE"})

    # 2. Magic MIME Type Validation
    mime_type = magic.from_buffer(image_bytes[:2048], mime=True)
    if mime_type not in ["image/jpeg", "image/png", "image/webp"]:
        return None, JSONResponse(status_code=400, content={"detail": f"Unsupported file format ({mime_type}). Only JPEG, PNG, and WebP are allowed.", "code": "INVALID_FILE"})

    # 3. Pillow Integrity Validation
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.verify()  # verify() catches truncated or invalid images without full loading
    except Exception:
        return None, JSONResponse(status_code=400, content={"detail": "File is corrupted or not a valid executable image matrix.", "code": "INVALID_FILE"})

    return image_bytes, None
