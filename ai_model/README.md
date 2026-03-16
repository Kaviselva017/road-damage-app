# AI Model – YOLOv8 Road Damage Detection

## Dataset
Use the Road Damage Dataset (RDD2022):
- Download: https://github.com/sekilab/RoadDamageDetector
- Or Kaggle: https://www.kaggle.com/datasets/felipenogueira/road-damage-dataset

Classes:
- D00: Longitudinal Crack
- D10: Transverse Crack  
- D20: Alligator Crack (Pothole-like)
- D40: Pothole

## Training (train_model.py)

```python
from ultralytics import YOLO

# Start from pretrained YOLOv8 weights
model = YOLO('yolov8m.pt')

results = model.train(
    data='rdd2022.yaml',   # Dataset config file
    epochs=50,
    imgsz=640,
    batch=16,
    name='road_damage_v1',
    device=0,              # GPU (use 'cpu' if no GPU)
    patience=10,
    save=True,
)

# After training, copy best weights:
# runs/detect/road_damage_v1/weights/best.pt → ai_model/road_damage_yolov8.pt
```

## Dataset YAML (rdd2022.yaml)

```yaml
path: ./datasets/rdd2022
train: images/train
val: images/val

nc: 4
names: ['longitudinal_crack', 'transverse_crack', 'alligator_crack', 'pothole']
```

## Inference Test

```python
from ultralytics import YOLO
model = YOLO('ai_model/road_damage_yolov8.pt')
results = model('test_image.jpg', conf=0.25)
results[0].show()
```

## Notes
- Without a trained model file, the system uses mock AI detection (random results for dev/testing)
- For production, train on RDD2022 dataset with at least 50 epochs on GPU
- Recommended: Google Colab (free GPU) or AWS EC2 p3.xlarge
