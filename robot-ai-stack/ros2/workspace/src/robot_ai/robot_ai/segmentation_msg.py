from geometry_msgs.msg import Point32
from sensor_msgs.msg import Image

from robot_ai_interfaces.msg import BBox2D, GrassSegment, GrassSegmentationArray


def build_segmentation_array(header, image_id: str, global_segments: list[dict]) -> GrassSegmentationArray:
    """Build bbox/polygon segmentation output in original-image coordinates."""
    arr = GrassSegmentationArray()
    arr.header = header
    arr.image_id = image_id
    for s in global_segments:
        x1, y1, x2, y2 = s["bbox"]
        seg = GrassSegment()
        seg.class_name = str(s["class_name"])
        seg.score = float(s["confidence"])

        bbox = BBox2D()
        bbox.center_x = float((x1 + x2) / 2.0)
        bbox.center_y = float((y1 + y2) / 2.0)
        bbox.size_x = float(x2 - x1)
        bbox.size_y = float(y2 - y1)
        bbox.theta = 0.0
        seg.bbox = bbox

        seg.mask = Image()
        for x, y in s.get("polygon", []):
            p = Point32()
            p.x = float(x)
            p.y = float(y)
            p.z = 0.0
            seg.polygon.points.append(p)
        arr.segments.append(seg)
    return arr
