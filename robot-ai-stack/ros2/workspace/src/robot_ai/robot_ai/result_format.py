def detections_to_list(arr) -> list[dict]:
    """vision_msgs/Detection2DArray → list dict (duck-typed để test không cần ROS2).

    Mỗi phần tử: class_name, score, bbox_xyxy [x1,y1,x2,y2], bbox_center [cx,cy], bbox_size [w,h].
    """
    out = []
    for det in arr.detections:
        c = det.bbox.center.position
        cx, cy = float(c.x), float(c.y)
        w, h = float(det.bbox.size_x), float(det.bbox.size_y)
        cls, score = "", 0.0
        if det.results:
            cls = str(det.results[0].hypothesis.class_id)
            score = float(det.results[0].hypothesis.score)
        out.append({
            "class_name": cls,
            "score": score,
            "bbox_xyxy": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
            "bbox_center": [cx, cy],
            "bbox_size": [w, h],
        })
    return out
