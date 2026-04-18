import io
from fastapi import UploadFile
from typing import Tuple
from PIL import Image

async def validate_image(file: UploadFile) -> Tuple[bool, str]:
    content = await file.read()
    await file.seek(0)
    
    if len(content) < 4:
        return False, "File too small"
        
    magic_bytes = content[:4]
    
    is_jpeg = magic_bytes[:3] == b"\xff\xd8\xff"
    is_png = magic_bytes == b"\x89\x50\x4e\x47"
    is_webp = magic_bytes == b"\x52\x49\x46\x46" # RIFF usually
    
    if not (is_jpeg or is_png or is_webp):
        return False, "Invalid image format (magic bytes mismatch)"
        
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
        if img.width < 224 or img.height < 224:
            return False, "Image dimensions must be at least 224x224"
    except Exception:
        return False, "Corrupted image file"
        
    return True, ""
