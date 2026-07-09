def segments_to_list(arr) -> list[dict]:
    """robot_ai_interfaces/GrassSegmentationArray → list dict (duck-typed, test không cần ROS2).

    Mỗi phần tử: class_name, score, bbox, polygon.points.
    """
    out = []
    for seg in arr.segments:
        b = seg.bbox
        out.append({
            "class_name": str(seg.class_name),
            "score": float(seg.score),
            "bbox": {
                "center_x": float(b.center_x),
                "center_y": float(b.center_y),
                "size_x": float(b.size_x),
                "size_y": float(b.size_y),
                "theta": float(b.theta),
            },
            "polygon": {
                "points": [
                    {"x": float(p.x), "y": float(p.y), "z": float(p.z)}
                    for p in seg.polygon.points
                ],
            },
        })
    return out
