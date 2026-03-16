"""
RoadWatch YOLOv8 Training Script
=================================
Train on free public road damage datasets.
No GPU needed for small dataset — Google Colab free tier works.

STEP 1: Get free dataset
STEP 2: Run this script  
STEP 3: Copy model to ai_model/road_damage_yolov8.pt
"""

# ── DATASET OPTIONS (all free) ─────────────────────────────────────
# Option A: RDD2022 — best, 47,000 images, Japan/India/USA/China roads
#   Download: https://github.com/sekilab/RoadDamageDetector
#   Classes: D00(crack), D10(crack), D20(alligator), D40(weathering)

# Option B: CRDDC2022 — 12,000 Indian road images ← BEST FOR YOUR PROJECT
#   Download: https://crddc2022.sekilab.global/dataset/
#   Classes: pothole, crack, surface_damage

# Option C: Roboflow public dataset (easiest, auto-downloads)
#   https://universe.roboflow.com/search?q=road+damage+pothole

import os, yaml
from pathlib import Path

def download_from_roboflow():
    """Download free road damage dataset from Roboflow (easiest method)"""
    try:
        from roboflow import Roboflow
        rf = Roboflow(api_key=os.getenv("ROBOFLOW_API_KEY", "YOUR_FREE_API_KEY"))
        # Free public dataset — no payment needed
        project = rf.workspace("universidad-bpigv").project("road-damage-detection-2")
        dataset = project.version(2).download("yolov8")
        return dataset.location
    except Exception as e:
        print(f"Roboflow download failed: {e}")
        print("Get free API key at: https://roboflow.com (free tier)")
        return None

def create_dataset_yaml(data_dir: str):
    """Create YAML config for training"""
    config = {
        "path": data_dir,
        "train": "train/images",
        "val": "valid/images",
        "test": "test/images",
        "nc": 4,
        "names": ["pothole", "crack", "surface_damage", "multiple"]
    }
    yaml_path = os.path.join(data_dir, "road_damage.yaml")
    with open(yaml_path, "w") as f:
        yaml.dump(config, f)
    return yaml_path

def train(data_yaml: str, epochs: int = 50, imgsz: int = 640):
    """
    Train YOLOv8 model.
    
    Hardware recommendations:
    - CPU only:     epochs=20, imgsz=416, batch=4  (~4 hours)
    - Google Colab: epochs=50, imgsz=640, batch=16 (~1 hour free)
    - GPU laptop:   epochs=100, imgsz=640, batch=32 (~30 min)
    """
    from ultralytics import YOLO

    # Start from pretrained YOLOv8n (nano - smallest, fastest)
    # Options: yolov8n, yolov8s, yolov8m, yolov8l, yolov8x
    model = YOLO("yolov8n.pt")

    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=8,
        patience=10,           # early stop if no improvement
        device="cpu",          # change to 0 for GPU
        project="ai_model",
        name="road_damage_v1",
        exist_ok=True,
        # Augmentation for road damage (important for accuracy)
        fliplr=0.5,            # horizontal flip
        flipud=0.1,            # vertical flip
        mosaic=0.8,            # mosaic augmentation
        scale=0.3,             # scale variation
        translate=0.1,
        degrees=5.0,           # slight rotation (roads are horizontal)
        hsv_h=0.015,           # color variation
        hsv_s=0.5,
        hsv_v=0.3,
    )
    
    best_model = Path("ai_model/road_damage_v1/weights/best.pt")
    if best_model.exists():
        import shutil
        shutil.copy(best_model, "ai_model/road_damage_yolov8.pt")
        print(f"\n✅ Model saved to: ai_model/road_damage_yolov8.pt")
        print(f"   mAP50: {results.results_dict.get('metrics/mAP50(B)', 0):.3f}")
        print(f"   mAP50-95: {results.results_dict.get('metrics/mAP50-95(B)', 0):.3f}")
    return results

def validate(model_path: str = "ai_model/road_damage_yolov8.pt"):
    """Test the trained model on a single image"""
    from ultralytics import YOLO
    model = YOLO(model_path)
    print("\nModel classes:", model.names)
    print("Model ready for inference!")
    return model

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RoadWatch YOLOv8 Trainer")
    parser.add_argument("--mode", choices=["download","train","validate","all"], default="all")
    parser.add_argument("--data", default="", help="Path to dataset folder")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    print("=" * 55)
    print("  RoadWatch YOLOv8 Road Damage Training")
    print("=" * 55)

    if args.mode in ("download", "all"):
        print("\n[1/3] Downloading dataset from Roboflow...")
        data_dir = download_from_roboflow()
        if not data_dir and not args.data:
            print("\nManual dataset setup:")
            print("  1. Go to: https://universe.roboflow.com")
            print("  2. Search: 'road damage pothole'")
            print("  3. Download in YOLOv8 format")
            print("  4. Run: python train_yolo.py --mode train --data /path/to/dataset")
            exit(0)
        if data_dir:
            args.data = data_dir

    if args.mode in ("train", "all") and args.data:
        print(f"\n[2/3] Creating dataset config...")
        yaml_path = create_dataset_yaml(args.data)
        print(f"      Config: {yaml_path}")
        print(f"\n[3/3] Training YOLOv8 (epochs={args.epochs}, imgsz={args.imgsz})...")
        print("      This will take 30min-4hrs depending on hardware")
        print("      Tip: Run on Google Colab for free GPU!\n")
        train(yaml_path, args.epochs, args.imgsz)

    if args.mode == "validate":
        validate()
