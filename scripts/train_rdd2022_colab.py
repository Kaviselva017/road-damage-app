"""
scripts/train_rdd2022_colab.py
================================
Google Colab training script for RoadWatch YOLOv8 on RDD2022.

Run all cells top-to-bottom in a Colab GPU (T4/A100) runtime.
Install: ultralytics==8.2.0, roboflow==1.1.29

Class mapping:
  D00 → longitudinal_crack (0)
  D10 → transverse_crack    (1)
  D20 → alligator_crack     (2)
  D40 → pothole             (3)
"""

# ╔══════════════════════════════════════════════════════════╗
# ║  CELL 1 — Install dependencies                          ║
# ╚══════════════════════════════════════════════════════════╝
# Paste as a code cell in Colab

INSTALL_CELL = """
!pip install ultralytics==8.2.0 roboflow==1.1.29 onnxruntime==1.18.0 --quiet
print("Packages installed ✓")
"""

# ╔══════════════════════════════════════════════════════════╗
# ║  CELL 2 — Mount Google Drive                            ║
# ╚══════════════════════════════════════════════════════════╝

DRIVE_CELL = """
from google.colab import drive
drive.mount('/content/drive')
import os
os.makedirs('/content/drive/MyDrive/road_damage', exist_ok=True)
print("Drive mounted ✓")
"""


# ╔══════════════════════════════════════════════════════════╗
# ║  CELL 3 — Script (run directly or paste into Colab)     ║
# ╚══════════════════════════════════════════════════════════╝

def main():
    import os
    import shutil
    import time

    import yaml

    # ── 1. Download dataset from Roboflow public workspace ──────────────────
    print("=" * 60)
    print("[1/6] Downloading RDD2022 dataset from Roboflow …")
    print("=" * 60)

    from roboflow import Roboflow  # noqa: PLC0415

    rf = Roboflow(api_key="")           # Public workspace — no key needed
    project = rf.workspace("rdd2022").project("road-damage-detection-uub4d")
    dataset = project.version(1).download("yolov8")

    dataset_dir = dataset.location  # e.g. /content/road-damage-detection-uub4d-1/
    print(f"Dataset downloaded to: {dataset_dir}")

    # ── 2. Write canonical data.yaml ────────────────────────────────────────
    print("\n[2/6] Writing data.yaml …")

    data_yaml_path = os.path.join(dataset_dir, "data.yaml")
    data_config = {
        "path": dataset_dir,
        "train": "train/images",
        "val":   "valid/images",
        "test":  "test/images",
        "nc": 4,
        "names": [
            "longitudinal_crack",   # D00
            "transverse_crack",     # D10
            "alligator_crack",      # D20
            "pothole",              # D40
        ],
    }

    with open(data_yaml_path, "w") as f:
        yaml.dump(data_config, f, default_flow_style=False)

    print(f"data.yaml written to: {data_yaml_path}")

    # ── 3. Train YOLOv8n ────────────────────────────────────────────────────
    print("\n[3/6] Training YOLOv8n for 100 epochs …")

    from ultralytics import YOLO  # noqa: PLC0415

    model = YOLO("yolov8n.pt")   # Automatically downloads nano weights

    results = model.train(
        data=data_yaml_path,
        epochs=100,
        imgsz=640,
        batch=16,
        project="roadwatch_runs",
        name="rdd2022",
        # ── Augmentation ────────────────────────────────────────────────────
        augment=True,
        mosaic=1.0,
        hsv_h=0.02,
        hsv_s=0.5,
        fliplr=0.5,
        degrees=5.0,
        # ── Misc ────────────────────────────────────────────────────────────
        device=0,          # GPU
        workers=4,
        patience=20,       # Early stop if no improvement for 20 epochs
        save=True,
        exist_ok=True,
        verbose=True,
    )

    # ── 4. Print final metrics ───────────────────────────────────────────────
    print("\n[4/6] Validation metrics:")
    metrics = model.val(data=data_yaml_path)

    map50    = metrics.box.map50
    map5095  = metrics.box.map

    print(f"  mAP50    : {map50:.4f}")
    print(f"  mAP50-95 : {map5095:.4f}")

    best_pt = "roadwatch_runs/rdd2022/weights/best.pt"

    # ── 5. Export to ONNX (opset 17) ─────────────────────────────────────────
    print("\n[5/6] Exporting to ONNX (opset=17) …")

    best_model = YOLO(best_pt)
    exported_path = best_model.export(format="onnx", opset=17, imgsz=640, dynamic=False)
    print(f"Exported: {exported_path}")

    best_onnx_local = "roadwatch_runs/rdd2022/weights/best.onnx"
    if os.path.abspath(str(exported_path)) != os.path.abspath(best_onnx_local):
        shutil.copy2(str(exported_path), best_onnx_local)

    # ── 6. Save to Google Drive ───────────────────────────────────────────────
    drive_dest = "/content/drive/MyDrive/road_damage/best.onnx"
    print(f"\n[6/6] Saving best.onnx to Drive → {drive_dest}")
    shutil.copy2(best_onnx_local, drive_dest)

    onnx_size_mb = os.path.getsize(best_onnx_local) / (1024 ** 2)

    # ── Checklist ─────────────────────────────────────────────────────────────
    map50_ok   = "✅" if map50   >= 0.72 else "❌"
    size_ok    = "✅" if onnx_size_mb < 20  else "❌"

    print("\n" + "=" * 60)
    print("POST-TRAINING CHECKLIST")
    print("=" * 60)
    print(f"  {map50_ok} mAP50 > 0.72         (got {map50:.4f})")
    print(f"  {size_ok} ONNX size < 20 MB    (got {onnx_size_mb:.2f} MB)")
    print("  ⬜ Copy best.onnx to ai_model/")
    print()
    print("  To copy locally, download from Drive and run:")
    print("    cp ai_model/best.onnx backend/  # or set YOLO_MODEL_PATH")
    print("=" * 60)

    if map50 >= 0.72:
        print("\nTRAINING SUCCESS 🎉")
    else:
        print(f"\nWARNING: mAP50 {map50:.4f} is below 0.72 target.")
        print("Consider: more epochs, larger model (yolov8s), or better data split.")


if __name__ == "__main__":
    # When run directly (not as a Colab cell walkthrough)
    main()
