def segments_to_list(arr) -> list[dict]:
    """robot_ai_interfaces/GrassSegmentationArray → list dict (duck-typed, test không cần ROS2).

    Mỗi phần tử: class_name, score, bbox_xyxy [x1,y1,x2,y2], bbox_center [cx,cy],
    bbox_size [w,h], polygon [[x,y], ...].
    """
    out = []
    for seg in arr.segments:
        b = seg.bbox
        cx, cy = float(b.center_x), float(b.center_y)
        w, h = float(b.size_x), float(b.size_y)
        polygon = [[float(p.x), float(p.y)] for p in seg.polygon.points]
        out.append({
            "class_name": str(seg.class_name),
            "score": float(seg.score),
            "bbox_xyxy": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
            "bbox_center": [cx, cy],
            "bbox_size": [w, h],
            "polygon": polygon,
        })
    return out
