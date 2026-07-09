import os

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from std_msgs.msg import Header

from robot_ai_interfaces.msg import GrassSegmentationArray, TileImage
from robot_ai.aggregator import DetectionAggregator
from robot_ai.detections import parse_detections
from robot_ai.geometry import BBox, local_to_global, point_local_to_global
from robot_ai.segmentation_msg import build_segmentation_array
from robot_ai.zmq_client import ZmqReqClient


class YoloBridge(Node):
    def __init__(self):
        super().__init__("yolo_bridge")
        port = os.environ.get("YOLO_ZMQ_PORT", "5555")
        endpoint = f"tcp://127.0.0.1:{port}"
        self._bridge = CvBridge()
        self._client = ZmqReqClient(endpoint, timeout_ms=2000)
        self._agg = DetectionAggregator(timeout_s=2.0)
        self._last_header = {}   # image_id -> Header (giữ header ảnh gốc để publish)
        self._sub = self.create_subscription(TileImage, "/image_tiles", self._on_tile, 10)
        self._seg_pub = self.create_publisher(GrassSegmentationArray, "/grass_segments", 10)
        self.create_timer(0.5, self._on_flush)
        self.get_logger().info(f"yolo_bridge → {endpoint}")

    def _on_tile(self, msg: TileImage):
        frame = self._bridge.imgmsg_to_cv2(msg.image, "bgr8")
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            self.get_logger().warning("imencode failed, skip tile")
            return
        reply = self._client.request(buf.tobytes())
        if reply is None:
            self.get_logger().warning("yolo_server timeout, socket recreated")
            return
        local = parse_detections(reply)
        global_dets = []
        for d in local:
            g = local_to_global(BBox(*d["bbox"]), msg.x_offset, msg.y_offset,
                                 msg.orig_width, msg.orig_height)
            polygon = [
                point_local_to_global(p[0], p[1], msg.x_offset, msg.y_offset, msg.orig_width, msg.orig_height)
                for p in d.get("polygon", [])
            ]
            global_dets.append({"class_name": d["class_name"], "confidence": d["confidence"],
                                "bbox": [g.x1, g.y1, g.x2, g.y2], "polygon": polygon})
        self._last_header[msg.image_id] = msg.header
        done = self._agg.add(msg.image_id, msg.tile_index, msg.num_tiles, global_dets)
        if done is not None:
            self._emit(msg.image_id, done)

    def _on_flush(self):
        for image_id, dets in self._agg.flush_expired():
            self._emit(image_id, dets)

    def _emit(self, image_id: str, dets: list):
        header = self._last_header.pop(image_id, Header())
        # Truy vết kết quả về đúng ảnh gốc: đưa image_id vào frame_id (giữ nguyên stamp).
        header.frame_id = image_id
        self._seg_pub.publish(build_segmentation_array(header, image_id, dets))
        self.get_logger().info(f"published {len(dets)} segments for image_id={image_id}")


def main():
    rclpy.init()
    node = YoloBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
