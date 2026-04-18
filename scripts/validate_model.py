"""
scripts/validate_model.py
===========================
Loads best.onnx locally, runs inference on 5 sample images from dataset/test/,
prints per-class confidence, draws bounding boxes with cv2, and exits with
code 1 if any class average confidence falls below 0.40.

Usage:
    python scripts/validate_model.py
    python scripts/validate_model.py --model ai_model/best.onnx --images dataset/test/images
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import glob
import random

import cv2
import numpy as np

CLASS_NAMES = {
    0: "longitudinal_crack",
    1: "transverse_crack",
    2: "alligator_crack",
    3: "pothole",
}

COLORS = {
    "longitudinal_crack": (0, 255, 255),   # yellow
    "transverse_crack":   (255, 0, 0),     # blue
    "alligator_crack":    (0, 165, 255),   # orange
    "pothole":            (0, 0, 255),     # red
}

CONF_THRESHOLD = 0.25
MIN_CLASS_AVG  = 0.40       # Exit-1 threshold


# ─────────────────────────────────────────────────────────────────────────────
# ONNX inference
# ─────────────────────────────────────────────────────────────────────────────

def load_session(onnx_path: str):
    import onnxruntime as ort  # noqa: PLC0415

    print(f"[validate] Loading: {onnx_path}")
    sess = ort.InferenceSession(onnx_path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    return sess


def preprocess(bgr: np.ndarray, size: int = 640) -> tuple[np.ndarray, float, float]:
    """Resize + normalise → (1,3,H,W) float32. Returns scale factors."""
    orig_h, orig_w = bgr.shape[:2]
    resized = cv2.resize(bgr, (size, size))
    blob = resized.astype(np.float32) / 255.0
    blob = np.transpose(blob, (2, 0, 1))[np.newaxis, ...]
    return blob, orig_w / size, orig_h / size


def postprocess(
    output: np.ndarray,     # (84, 8400)
    scale_x: float,
    scale_y: float,
    conf_thresh: float = CONF_THRESHOLD,
) -> list[dict]:
    boxes_raw = output[:4, :].T       # (8400, 4)  cx cy w h (in 640px space)
    scores    = output[4:, :].T       # (8400, num_classes)

    detections = []
    for i in range(scores.shape[0]):
        class_id = int(np.argmax(scores[i]))
        conf     = float(scores[i, class_id])
        if conf < conf_thresh:
            continue
        cx, cy, bw, bh = boxes_raw[i]
        x1 = int((cx - bw / 2) * scale_x)
        y1 = int((cy - bh / 2) * scale_y)
        x2 = int((cx + bw / 2) * scale_x)
        y2 = int((cy + bh / 2) * scale_y)
        detections.append({
            "class_id":   class_id,
            "class_name": CLASS_NAMES.get(class_id, f"cls_{class_id}"),
            "confidence": round(conf, 4),
            "bbox":       [x1, y1, x2, y2],
        })
    return sorted(detections, key=lambda d: d["confidence"], reverse=True)


def draw_boxes(bgr: np.ndarray, detections: list[dict]) -> np.ndarray:
    vis = bgr.copy()
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        color = COLORS.get(det["class_name"], (200, 200, 200))
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        label = f"{det['class_name']} {det['confidence']:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(vis, (x1, y1 - th - 4), (x1 + tw + 2, y1), color, -1)
        cv2.putText(vis, label, (x1 + 1, y1 - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return vis


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Validate best.onnx on test images")
    parser.add_argument("--model",  default="ai_model/best.onnx",
                        help="Path to best.onnx")
    parser.add_argument("--images", default="dataset/test/images",
                        help="Directory of test images")
    parser.add_argument("--n",      type=int, default=5,
                        help="Number of images to sample")
    parser.add_argument("--save",   default="validation_output",
                        help="Directory to save annotated images")
    parser.add_argument("--show",   action="store_true",
                        help="Display images in cv2 window (requires display)")
    args = parser.parse_args()

    # Validate paths
    if not os.path.exists(args.model):
        print(f"[validate] ERROR: ONNX model not found at '{args.model}'")
        print("           Run scripts/export_onnx.py first.")
        sys.exit(1)

    if not os.path.isdir(args.images):
        print(f"[validate] ERROR: image directory not found: '{args.images}'")
        print("           Expected structure: dataset/test/images/")
        sys.exit(1)

    exts   = ("*.jpg", "*.jpeg", "*.png", "*.webp")
    all_imgs = []
    for ext in exts:
        all_imgs.extend(glob.glob(os.path.join(args.images, ext)))

    if not all_imgs:
        print(f"[validate] ERROR: No images found in '{args.images}'")
        sys.exit(1)

    sample = random.sample(all_imgs, min(args.n, len(all_imgs)))
    print(f"[validate] {len(all_imgs)} test images found — sampling {len(sample)}")

    sess = load_session(args.model)
    input_name = sess.get_inputs()[0].name
    os.makedirs(args.save, exist_ok=True)

    # Per-class confidence tracking
    class_confidences: dict[str, list[float]] = {v: [] for v in CLASS_NAMES.values()}
    total_detections = 0

    for idx, img_path in enumerate(sample, 1):
        bgr = cv2.imread(img_path)
        if bgr is None:
            print(f"  [{idx}] SKIP (couldn't read): {os.path.basename(img_path)}")
            continue

        blob, sx, sy = preprocess(bgr)

        t0  = time.perf_counter()
        out = sess.run(None, {input_name: blob})
        ms  = (time.perf_counter() - t0) * 1000

        dets = postprocess(out[0][0], sx, sy)
        total_detections += len(dets)

        print(f"\n  [{idx}] {os.path.basename(img_path)}  ({ms:.1f} ms)  → {len(dets)} detection(s)")
        for det in dets:
            print(f"        {det['class_name']:<22} conf={det['confidence']:.4f}  bbox={det['bbox']}")
            class_confidences[det["class_name"]].append(det["confidence"])

        vis = draw_boxes(bgr, dets)
        out_path = os.path.join(args.save, f"result_{idx:02d}_{os.path.basename(img_path)}")
        cv2.imwrite(out_path, vis)

        if args.show:
            cv2.imshow("RoadWatch Validation", vis)
            cv2.waitKey(800)

    if args.show:
        cv2.destroyAllWindows()

    # ── Per-class summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("PER-CLASS CONFIDENCE SUMMARY")
    print("=" * 60)
    failed_classes = []
    for cls_name, confs in class_confidences.items():
        if not confs:
            print(f"  {cls_name:<22}  — no detections")
            continue
        avg = sum(confs) / len(confs)
        status = "✅" if avg >= MIN_CLASS_AVG else "❌"
        print(f"  {status} {cls_name:<22}  avg={avg:.4f}  n={len(confs)}")
        if avg < MIN_CLASS_AVG:
            failed_classes.append(cls_name)

    print(f"\nTotal detections : {total_detections}")
    print(f"Images processed : {len(sample)}")
    print(f"Annotated saved  : {args.save}/")

    if failed_classes:
        print(f"\n❌ FAIL: Classes below {MIN_CLASS_AVG} avg confidence: {failed_classes}")
        sys.exit(1)
    else:
        print(f"\n✅ PASS: All detected classes ≥ {MIN_CLASS_AVG} avg confidence")
        print("5 images processed, no exit 1")


if __name__ == "__main__":
    main()
