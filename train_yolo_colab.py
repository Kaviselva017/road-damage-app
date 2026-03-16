# ═══════════════════════════════════════════════════════════════
# RoadWatch YOLOv8 Training Script
# Run on Google Colab: https://colab.research.google.com
# Runtime → Change runtime type → T4 GPU → Run All
# ═══════════════════════════════════════════════════════════════

# ━━━ CELL 1: Install Dependencies ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
!pip install ultralytics roboflow -q
import ultralytics
ultralytics.checks()
import torch
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No GPU - switch to T4!'}")
"""

# ━━━ CELL 2: Download Free Road Damage Dataset ━━━━━━━━━━━━━━━━━
"""
# Sign up FREE at https://roboflow.com then get your API key
from roboflow import Roboflow

# Free road damage dataset — 4 classes: pothole, crack, surface_damage, multiple
rf = Roboflow(api_key="oYclFlphlbxaiTNVdoMp")
project = rf.workspace("pothole-jfhne").project("pothole-detection-tdpan")
dataset = project.version(1).download("yolov8")
DATASET_PATH = dataset.location + "/data.yaml"
print("Dataset ready at:", DATASET_PATH)
"""

# ━━━ CELL 3: OR Use Alternative Free Dataset ━━━━━━━━━━━━━━━━━━━
"""
# Alternative: Download directly without Roboflow
import os, yaml

os.makedirs('road_dataset/train/images', exist_ok=True)
os.makedirs('road_dataset/train/labels', exist_ok=True)
os.makedirs('road_dataset/valid/images', exist_ok=True)
os.makedirs('road_dataset/valid/labels', exist_ok=True)

# Download CRDDC2022 India road damage dataset
!wget -q "https://github.com/sekilab/RoadDamageDetector/releases/download/dataset/RoadDamageDataset2022.tar.gz"
!tar -xzf RoadDamageDataset2022.tar.gz -C road_dataset/ 2>/dev/null || echo "Extract manually"

# Create YAML config
config = {
    'path': '/content/road_dataset',
    'train': 'train/images',
    'val': 'valid/images',
    'nc': 4,
    'names': ['pothole', 'crack', 'surface_damage', 'multiple_damage']
}
with open('road_dataset/data.yaml', 'w') as f:
    yaml.dump(config, f)

DATASET_PATH = '/content/road_dataset/data.yaml'
print("Dataset ready!")
"""

# ━━━ CELL 4: TRAIN YOLOv8 Model ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from ultralytics import YOLO

# Load YOLOv8 nano (fastest training, good accuracy)
model = YOLO('yolov8n.pt')

results = model.train(
    data=DATASET_PATH,
    epochs=50,        # ~2 hours on free Colab GPU
    imgsz=640,
    batch=16,
    name='roadwatch_v1',
    project='/content/roadwatch',
    patience=15,
    save=True,
    plots=True,
    fliplr=0.5,
    mosaic=1.0,
    mixup=0.1,
    degrees=5.0,
)

print("Training complete!")
print("Best model:", results.save_dir + '/weights/best.pt')
"""

# ━━━ CELL 5: Check Accuracy ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from ultralytics import YOLO

model = YOLO('/content/roadwatch/roadwatch_v1/weights/best.pt')
metrics = model.val()

print("="*40)
print(f"mAP@50:      {metrics.box.map50:.1%}")
print(f"mAP@50-95:   {metrics.box.map:.1%}")
print(f"Precision:   {metrics.box.mp:.1%}")
print(f"Recall:      {metrics.box.mr:.1%}")
print("="*40)

# Good results: mAP@50 > 0.60 = good, > 0.75 = excellent
"""

# ━━━ CELL 6: Download Model ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import shutil
from google.colab import files

shutil.copy(
    '/content/roadwatch/roadwatch_v1/weights/best.pt',
    '/content/road_damage_yolov8.pt'
)
files.download('/content/road_damage_yolov8.pt')

print("Model downloaded!")
print("Now copy to: D:\\python\\road-damage-app\\backend\\ai_model\\road_damage_yolov8.pt")
"""

# ━━━ CELL 7: Test on Road Image ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from ultralytics import YOLO
from PIL import Image
import requests
from io import BytesIO

model = YOLO('/content/road_damage_yolov8.pt')

# Test with a road damage image from internet
url = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Pothole_on_rural_road.jpg/640px-Pothole_on_rural_road.jpg"
img = Image.open(BytesIO(requests.get(url).content))
img.save('/content/test_road.jpg')

results = model('/content/test_road.jpg', conf=0.25)
results[0].show()

for r in results:
    for box in r.boxes:
        print(f"Detected: {model.names[int(box.cls[0])]} | Confidence: {float(box.conf[0]):.1%}")
"""
