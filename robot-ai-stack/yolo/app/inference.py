import cv2
import numpy as np


def decode_jpeg(data: bytes):
    """Giải mã JPEG → BGR ndarray; None nếu rỗng/hỏng."""
    if not data:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def run_inference(model, img, target_classes=None) -> list[dict]:
    """Chạy YOLO trên ảnh BGR → list detection toạ độ LOCAL (trong tile)."""
    if img is None:
        return []
    dets = []
    for r in model(img, verbose=False):
        for box in r.boxes:
            cls = int(box.cls[0])
            name = model.names[cls]
            if target_classes and name not in target_classes:
                continue
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
            dets.append({
                "class_id": cls,
                "class_name": name,
                "confidence": float(box.conf[0]),
                "bbox": [x1, y1, x2, y2],
            })
    return dets
