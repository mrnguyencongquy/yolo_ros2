import cv2
import numpy as np


def decode_jpeg(data: bytes):
    """Giải mã JPEG → BGR ndarray; None nếu rỗng/hỏng."""
    if not data:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def run_inference(model, img, target_classes=None) -> list[dict]:
    """Chạy YOLO trên ảnh BGR → list detection/segment toạ độ LOCAL (trong tile)."""
    if img is None:
        return []
    dets = []
    for r in model(img, verbose=False):
        masks_xy = r.masks.xy if getattr(r, "masks", None) is not None and r.masks is not None else None
        for i, box in enumerate(r.boxes):
            cls = int(box.cls[0])
            name = model.names[cls]
            if target_classes and name not in target_classes:
                continue
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
            polygon = []
            if masks_xy is not None and i < len(masks_xy):
                polygon = [[float(x), float(y)] for x, y in masks_xy[i]]
            dets.append({
                "class_id": cls,
                "class_name": name,
                "confidence": float(box.conf[0]),
                "bbox": [x1, y1, x2, y2],
                "polygon": polygon,
            })
    return dets
