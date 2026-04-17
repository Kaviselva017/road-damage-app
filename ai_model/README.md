# RoadWatch — AI Model Training

## Overview

This directory contains the YOLOv8 model weights and the Google Colab training
notebook for the RoadWatch road damage detection system.

## Files

| File | Description |
|------|-------------|
| `train_rdd2022.ipynb` | Complete Colab notebook — downloads RDD2022, trains YOLOv8n, evaluates, and exports `best.pt` to Google Drive |
| `road_damage_yolov8.pt` | Trained YOLOv8n weights (referenced by the backend via `YOLO_MODEL_PATH`) |

## Detection Classes

| Index | Class Name | RDD2022 Code | Description |
|-------|-----------|--------------|-------------|
| 0 | `pothole` | D40 | Road surface depression / pothole |
| 1 | `crack` | D00, D10 | Longitudinal & transverse cracking |
| 2 | `surface_damage` | D20 | Alligator / weathering / surface deterioration |
| 3 | `multiple` | (composite) | ≥ 2 distinct damage types in one image |

## Training Pipeline

### Quick Start (Google Colab)

1. Open `train_rdd2022.ipynb` in Google Colab
2. Set runtime to **GPU → T4** or better
3. Run all 6 cells in order:
   - **Cell 1** — Install `ultralytics`, `gdown`, `albumentations`; mount Drive
   - **Cell 2** — Download & extract RDD2022 dataset via `gdown`
   - **Cell 3** — Auto-detect dataset splits and generate `data.yaml`
   - **Cell 4** — Train YOLOv8n for 50 epochs (batch=16, imgsz=640)
   - **Cell 5** — Print mAP@50, mAP@50-95; copy `best.pt` to Google Drive
   - **Cell 6** — Validate inference on 3 random val images
4. Download `best.pt` from Drive → place here as `road_damage_yolov8.pt`

### Training Hyperparameters

```
epochs:    50
imgsz:     640
batch:     16
patience:  10
mosaic:    1.0
flipud:    0.3
fliplr:    0.5
hsv_h:     0.015
backbone:  yolov8n.pt (pretrained COCO nano)
```

## Backend Integration

The backend loads the model via the `YOLO_MODEL_PATH` environment variable:

```bash
# .env
YOLO_MODEL_PATH=../ai_model/road_damage_yolov8.pt
```

If the model file is missing, `ai_service.py` falls back to a **deterministic
mock** that returns consistent results per-image (seeded by file content hash).
Mock results are prefixed with `[MOCK]` in the description field.

### Severity Mapping

| Confidence Range | Severity |
|-----------------|----------|
| ≥ 0.80 | `high` |
| ≥ 0.55 | `medium` |
| < 0.55 | `low` |

### API Contract

`ai_service.analyze_image(path)` returns:

```json
{
  "damage_type":   "pothole | crack | surface_damage | multiple",
  "severity":      "high | medium | low",
  "ai_confidence": 0.85,
  "description":   "High severity pothole detected with 85% confidence."
}
```
