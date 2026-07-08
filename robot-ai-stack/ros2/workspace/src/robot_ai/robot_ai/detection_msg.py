from vision_msgs.msg import (
    BoundingBox2D,
    Detection2D,
    Detection2DArray,
    ObjectHypothesisWithPose,
)


def build_detection_array(header, global_dets: list[dict]) -> Detection2DArray:
    """global_dets: [{class_name, confidence, bbox:[x1,y1,x2,y2] GLOBAL}] → Detection2DArray."""
    arr = Detection2DArray()
    arr.header = header
    for d in global_dets:
        x1, y1, x2, y2 = d["bbox"]
        det = Detection2D()
        det.header = header
        bbox = BoundingBox2D()
        bbox.center.position.x = (x1 + x2) / 2.0
        bbox.center.position.y = (y1 + y2) / 2.0
        bbox.size_x = float(x2 - x1)
        bbox.size_y = float(y2 - y1)
        det.bbox = bbox
        hyp = ObjectHypothesisWithPose()
        hyp.hypothesis.class_id = str(d["class_name"])
        hyp.hypothesis.score = float(d["confidence"])
        det.results.append(hyp)
        arr.detections.append(det)
    return arr
