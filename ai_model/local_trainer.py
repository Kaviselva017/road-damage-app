import os
import sys
import shutil
import glob
import random
import yaml
import zipfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# Verify ultralytics is installed
try:
    from ultralytics import YOLO
except ImportError:
    print("ultralytics not found. Please run 'pip install ultralytics'.")
    sys.exit(1)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "rdd2022"))
YAML_PATH = os.path.join(BASE_DIR, "data.yaml")

os.makedirs(BASE_DIR, exist_ok=True)

# 1. Download Datasets
ZIP_URL = "https://ndownloader.figshare.com/files/38030910"
ZIP_NAME = "RDD2022_released_through_CRDDC2022.zip"
zip_path = os.path.join(BASE_DIR, ZIP_NAME)
dest = os.path.join(BASE_DIR, "raw_dataset")

if not os.path.exists(dest):
    if not os.path.exists(zip_path):
        print(f"⬇️ Downloading Full RDD2022 Dataset (this may take a while, GBs of data)...")
        def reporthook(block_num, block_size, total_size):
            read_so_far = block_num * block_size
            if total_size > 0:
                percent = read_so_far * 1e2 / total_size
                s = f"\r{percent:5.1f}% [{read_so_far / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB]"
                sys.stdout.write(s)
                if read_so_far >= total_size:
                    sys.stdout.write('\n')
        
        urllib.request.urlretrieve(ZIP_URL, zip_path, reporthook)
    
    print(f"📦 Extracting {ZIP_NAME} ...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(dest)
    os.remove(zip_path)
    print(f"✅ Extraction complete")
else:
    print(f"ℹ️ Dataset already extracted")

# 2. Data Preparation
print("🔍 Scanning extracted files...")
all_imgs = []
for ext in ('*.jpg', '*.jpeg', '*.png'):
    all_imgs.extend(glob.glob(os.path.join(BASE_DIR, 'raw_*', '**', 'train', 'images', ext), recursive=True))

all_xmls = glob.glob(os.path.join(BASE_DIR, 'raw_*', '**', 'train', 'annotations', 'xmls', '*.xml'), recursive=True)

print(f"Total images : {len(all_imgs)}")
print(f"Total XMLs   : {len(all_xmls)}")

RAW_CLASS_MAP = {
    'D00': 'crack', 'D01': 'crack', 'D10': 'crack', 'D11': 'crack',
    'D20': 'surface_damage', 'D40': 'pothole', 'D44': 'pothole',
    'D43': 'pothole', 'D50': 'surface_damage', 'D0w0': 'crack',
}
CLASS_NAMES = ['pothole', 'crack', 'surface_damage', 'multiple']

def xml_to_yolo(xml_path, img_w, img_h):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    lines = []
    classes_in_image = set()
    
    for obj in root.findall('object'):
        raw_name = obj.find('name').text.strip()
        if cls_name := RAW_CLASS_MAP.get(raw_name):
            classes_in_image.add(cls_name)
            
    is_multiple = len(classes_in_image) > 1

    for obj in root.findall('object'):
        raw_name = obj.find('name').text.strip()
        cls_name = RAW_CLASS_MAP.get(raw_name)
        if not cls_name: continue
            
        cls_id = 3 if is_multiple else CLASS_NAMES.index(cls_name)
            
        bndbox = obj.find('bndbox')
        xmin, ymin = float(bndbox.find('xmin').text), float(bndbox.find('ymin').text)
        xmax, ymax = float(bndbox.find('xmax').text), float(bndbox.find('ymax').text)
        
        cx, cy = ((xmin + xmax) / 2) / img_w, ((ymin + ymax) / 2) / img_h
        bw, bh = (xmax - xmin) / img_w, (ymax - ymin) / img_h
        
        cx, cy, bw, bh = [round(min(max(v, 0.0), 1.0), 6) for v in [cx, cy, bw, bh]]
        if bw > 0 and bh > 0:
            lines.append(f"{cls_id} {cx} {cy} {bw} {bh}")
    return lines

for split in ['train', 'val']:
    os.makedirs(os.path.join(BASE_DIR, 'images', split), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'labels', split), exist_ok=True)

pairs = []
xml_index = {Path(x).stem: x for x in all_xmls}

for img_path in all_imgs:
    stem = Path(img_path).stem
    if stem in xml_index:
        pairs.append((img_path, xml_index[stem]))

print(f"Matched image+label pairs: {len(pairs)}")

random.seed(42)
random.shuffle(pairs)
split_idx = int(len(pairs) * 0.8)
train_pairs = pairs[:split_idx]
val_pairs = pairs[split_idx:]

from PIL import Image

print("⚙️ Processing images and annotations into YOLO format (this will take a few minutes)...")
skipped = 0
for split_name, split_pairs in [('train', train_pairs), ('val', val_pairs)]:
    for img_path, xml_path in split_pairs:
        try:
            with Image.open(img_path) as im:
                w, h = im.size
            yolo_lines = xml_to_yolo(xml_path, w, h)
            if not yolo_lines:
                skipped += 1
                continue
            fname = Path(img_path).name
            shutil.copy(img_path, os.path.join(BASE_DIR, 'images', split_name, fname))
            
            label_path = os.path.join(BASE_DIR, 'labels', split_name, f"{Path(img_path).stem}.txt")
            with open(label_path, 'w') as lf:
                lf.write('\n'.join(yolo_lines))
        except Exception:
            skipped += 1

print(f"\nTrain: {len(glob.glob(os.path.join(BASE_DIR, 'images', 'train', '*')))} images")
print(f"Val  : {len(glob.glob(os.path.join(BASE_DIR, 'images', 'val', '*')))} images")
print(f"Skip : {skipped} (no valid boxes or read errors)")

with open(YAML_PATH, 'w') as f:
    yaml.dump({
        'path' : BASE_DIR,
        'train': 'images/train',
        'val'  : 'images/val',
        'nc'   : 4,
        'names': CLASS_NAMES,
    }, f, default_flow_style=False)

print("\n🚀 Starting YOLOv8 Training...")
# Try to determine if CUDA is available, otherwise default to CPU
import torch
device = 0 if torch.cuda.is_available() else 'cpu'
if device == 'cpu':
    print("⚠️ WARNING: CUDA not detected! Training on CPU will be extremely slow. It could take several days.")

model = YOLO("yolov8n.pt")

results = model.train(
    data=YAML_PATH,
    epochs=50,
    imgsz=640,
    batch=16,
    patience=10,
    mosaic=1.0,
    flipud=0.3,
    fliplr=0.5,
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    translate=0.1,
    scale=0.5,
    degrees=5.0,
    project=os.path.join(BASE_DIR, "runs"),
    name='roadwatch',
    exist_ok=True,
    device=device,
    workers=0 if os.name == 'nt' else 2, # Windows avoids dataloader crash with workers=0
    cache=True,
    optimizer='AdamW',
    lr0=0.001,
    lrf=0.01,
    weight_decay=0.0005,
    warmup_epochs=3,
    close_mosaic=10,
    amp=True,
)

print(f"\n✅ Training complete")
BEST_PT = os.path.join(BASE_DIR, "runs", "roadwatch", "weights", "best.pt")
print(f"Best weights have been successfully saved to: {BEST_PT}")
