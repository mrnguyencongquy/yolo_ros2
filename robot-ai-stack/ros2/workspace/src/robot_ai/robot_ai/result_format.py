def instances_to_list(arr) -> list[dict]:
    """robot_ai_interfaces/DetectedInstanceArray → list dict (duck-typed, test không cần ROS2).

    Mỗi phần tử: class_name, score, bbox, polygon.points.
    """
    out = []
    for instance in arr.instances:
        b = instance.bbox
        out.append({
            "class_name": str(instance.class_name),
            "score": float(instance.score),
            "bbox": {
                "center_x": float(b.center_x),
                "center_y": float(b.center_y),
                "size_x": float(b.size_x),
                "size_y": float(b.size_y),
            },
            "polygon": {
                "points": [
                    {"x": float(p.x), "y": float(p.y)}
                    for p in instance.polygon.points
                ],
            },
        })
    return out
