"""
scripts/export_onnx.py
========================
Exports best.pt → ai_model/best.onnx (opset 17).
Runs dummy inference and prints shape + latency.
Prints "EXPORT OK" on success.

Usage:
    python scripts/export_onnx.py
    python scripts/export_onnx.py --model ai_model/runs/roadwatch/weights/best.pt
"""

from __future__ import annotations

import argparse
import os
import time

import numpy as np


def export(model_path: str, output_path: str, opset: int = 17) -> None:
    from ultralytics import YOLO  # noqa: PLC0415

    print(f"[export_onnx] Loading model from: {model_path}")
    model = YOLO(model_path)

    print(f"[export_onnx] Exporting to ONNX (opset={opset}) …")
    exported = model.export(format="onnx", opset=opset, dynamic=False, imgsz=640)
    print(f"[export_onnx] Exported path reported by ultralytics: {exported}")

    # Move/copy to desired output_path if different
    if os.path.abspath(str(exported)) != os.path.abspath(output_path):
        import shutil  # noqa: PLC0415

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        shutil.copy2(str(exported), output_path)
        print(f"[export_onnx] Copied to: {output_path}")


def validate_onnx(onnx_path: str) -> None:
    import onnxruntime as ort  # noqa: PLC0415

    print(f"[export_onnx] Loading ONNX session from: {onnx_path}")
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    input_shape = sess.get_inputs()[0].shape  # e.g. [1, 3, 640, 640]
    print(f"[export_onnx] Input  name : {input_name}")
    print(f"[export_onnx] Input  shape: {input_shape}")

    # Dummy inference
    dummy = np.random.rand(1, 3, 640, 640).astype(np.float32)
    t0 = time.perf_counter()
    out = sess.run(None, {input_name: dummy})
    latency_ms = (time.perf_counter() - t0) * 1000

    print(f"[export_onnx] Output shape: {[o.shape for o in out]}")
    print(f"[export_onnx] Latency     : {latency_ms:.1f} ms (CPU, single image)")

    size_mb = os.path.getsize(onnx_path) / (1024 ** 2)
    print(f"[export_onnx] File size   : {size_mb:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="Export YOLOv8 .pt → .onnx")
    parser.add_argument(
        "--model",
        default="ai_model/runs/roadwatch/weights/best.pt",
        help="Path to best.pt",
    )
    parser.add_argument(
        "--output",
        default="ai_model/best.onnx",
        help="Output path for best.onnx",
    )
    parser.add_argument("--opset", type=int, default=17)
    args = parser.parse_args()

    if not os.path.exists(args.model):
        raise FileNotFoundError(
            f"Model not found: {args.model}\n"
            "Run the full training first (scripts/train_rdd2022_colab.py in Colab)."
        )

    export(args.model, args.output, opset=args.opset)
    validate_onnx(args.output)
    print("\nEXPORT OK")


if __name__ == "__main__":
    main()
