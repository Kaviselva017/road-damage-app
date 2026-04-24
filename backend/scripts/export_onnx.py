#!/usr/bin/env python3
"""
Export YOLOv8 .pt model to ONNX format.
Usage: python scripts/export_onnx.py --model ai_model/best.pt
"""
import argparse
import sys
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, help='Path to best.pt')
    parser.add_argument('--opset', type=int, default=17)
    args = parser.parse_args()
    
    if not os.path.exists(args.model):
        print(f"ERROR: Model not found: {args.model}")
        sys.exit(1)
    
    try:
        from ultralytics import YOLO
        from pathlib import Path
        
        pt = Path(args.model)
        model = YOLO(str(pt))
        model.export(
            format='onnx',
            imgsz=640,
            simplify=True,
            opset=args.opset,
            dynamic=False,
        )
        onnx_path = pt.with_suffix('.onnx')
        size_mb = onnx_path.stat().st_size / 1024 / 1024
        print(f"✅ Exported: {onnx_path}")
        print(f"   Size: {size_mb:.1f} MB")
        print(f"   Set env var: YOLO_MODEL_PATH={args.model}")
        print(f"   ONNX will auto-load from: {onnx_path}")
    
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
