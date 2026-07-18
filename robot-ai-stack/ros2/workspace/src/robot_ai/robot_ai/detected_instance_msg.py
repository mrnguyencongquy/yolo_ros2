from geometry_msgs.msg import Point32

from robot_ai_interfaces.msg import BBox2D, DetectedInstance, DetectedInstanceArray


def build_detected_instance_array(
    header, image_id: str, global_instances: list[dict]
) -> DetectedInstanceArray:
    """Build detected-instance output in original-image coordinates."""
    arr = DetectedInstanceArray()
    arr.header = header
    arr.image_id = image_id
    for instance in global_instances:
        x1, y1, x2, y2 = instance["bbox"]
        detected = DetectedInstance()
        detected.class_name = str(instance["class_name"])
        detected.score = float(instance["confidence"])

        bbox = BBox2D()
        bbox.center_x = float((x1 + x2) / 2.0)
        bbox.center_y = float((y1 + y2) / 2.0)
        bbox.size_x = float(x2 - x1)
        bbox.size_y = float(y2 - y1)
        detected.bbox = bbox

        for x, y in instance.get("polygon", []):
            p = Point32()
            p.x = float(x)
            p.y = float(y)
            detected.polygon.points.append(p)
        arr.instances.append(detected)
    return arr
