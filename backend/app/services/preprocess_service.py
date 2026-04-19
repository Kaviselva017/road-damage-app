import cv2
from pathlib import Path
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

CLAHE_ENABLED = os.getenv("CLAHE_ENABLED", "true").lower() == "true"
TTA_ENABLED   = os.getenv("TTA_ENABLED",   "false").lower() == "true"
CLAHE_CLIP    = float(os.getenv("CLAHE_CLIP_LIMIT", "2.0"))
CLAHE_GRID    = int(os.getenv("CLAHE_GRID_SIZE", "8"))

def apply_clahe(image_path: str) -> str:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    to improve detection on dark, wet, or overexposed road images.
    
    Returns path to preprocessed temp image.
    Original image is NOT modified.
    
    Steps:
    1. Read image with cv2
    2. Convert BGR → LAB colorspace
    3. Apply CLAHE to L channel only (preserves color, enhances contrast)
    4. Convert LAB → BGR
    5. Save to temp file
    6. Return temp file path
    """
    img = cv2.imread(image_path)
    if img is None:
        logger.warning("CLAHE: could not read %s — skipping", image_path)
        return image_path
    
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    
    clahe = cv2.createCLAHE(
        clipLimit=CLAHE_CLIP,
        tileGridSize=(CLAHE_GRID, CLAHE_GRID)
    )
    l_enhanced = clahe.apply(l_ch)
    
    enhanced = cv2.merge([l_enhanced, a_ch, b_ch])
    result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    
    suffix = Path(image_path).suffix or ".jpg"
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=f"_clahe{suffix}"
    )
    cv2.imwrite(tmp.name, result)
    return tmp.name

def generate_tta_variants(image_path: str) -> list[str]:
    """
    Generate Test-Time Augmentation variants for ensemble inference.
    Returns list of temp file paths for:
    - original
    - horizontal flip
    - brightness +20
    - brightness -20
    
    Caller is responsible for deleting temp files.
    """
    img = cv2.imread(image_path)
    if img is None:
        return [image_path]
    
    variants = []
    configs = [
        ('orig',    img),
        ('hflip',   cv2.flip(img, 1)),
        ('bright+', cv2.convertScaleAbs(img, alpha=1.0, beta=20)),
        ('bright-', cv2.convertScaleAbs(img, alpha=1.0, beta=-20)),
    ]
    
    suffix = Path(image_path).suffix or ".jpg"
    for name, variant in configs:
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=f"_{name}{suffix}"
        )
        cv2.imwrite(tmp.name, variant)
        variants.append(tmp.name)
    
    return variants

def preprocess_for_inference(image_path: str) -> tuple[str, list[str]]:
    """
    Main entry point. Returns:
    - primary_path: CLAHE-enhanced image path (use for single inference)
    - tta_paths: list of variant paths (use for TTA ensemble)
    
    Caller must delete all returned temp files.
    """
    primary = apply_clahe(image_path) if CLAHE_ENABLED else image_path
    
    if TTA_ENABLED:
        tta_paths = generate_tta_variants(primary)
    else:
        tta_paths = [primary]
    
    return primary, tta_paths
