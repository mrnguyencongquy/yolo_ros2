import json


def parse_detections(raw: bytes) -> list[dict]:
    """Parse reply JSON của yolo_server. Bỏ detection méo mó, trả [] nếu JSON hỏng."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for d in data:
        if not isinstance(d, dict):
            continue
        bbox = d.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        try:
            out.append({
                "class_id": int(d.get("class_id", -1)),
                "class_name": str(d.get("class_name", "")),
                "confidence": float(d.get("confidence", 0.0)),
                "bbox": [float(v) for v in bbox],
            })
        except (TypeError, ValueError):
            continue
    return out
