import json
import os

import cv2
import numpy as np
import rclpy
from rclpy.node import Node

from robot_ai_interfaces.msg import GrassSegmentationArray
from robot_ai.result_format import segments_to_list


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


class ResultWriter(Node):
    """Downstream: lưu kết quả /grass_segments mới nhất ra file để kiểm/verify.

    Mặc định bật trong docker compose để vận hành dev/test thấy ngay output mới nhất.
      RESULT_SAVE=0        tắt lưu khi production không cần file
      RESULT_FORMAT=json|annotated|both
      RESULT_DIR=/output   (mount ./shared/output)
      SAMPLE_DIR=/images   (nguồn ảnh gốc cho annotate ở dev)
    """

    def __init__(self):
        super().__init__("result_writer")
        self.declare_parameter("save", _truthy(os.environ.get("RESULT_SAVE", "0")))
        self.declare_parameter("format", os.environ.get("RESULT_FORMAT", "json"))
        self.declare_parameter("out_dir", os.environ.get("RESULT_DIR", "/output"))
        self.declare_parameter("sample_dir", os.environ.get("SAMPLE_DIR", "/images"))

        self._save = self.get_parameter("save").value
        self._format = self.get_parameter("format").value
        self._out = self.get_parameter("out_dir").value
        self._sample_dir = self.get_parameter("sample_dir").value

        if self._save:
            os.makedirs(self._out, exist_ok=True)
        self.create_subscription(GrassSegmentationArray, "/grass_segments", self._on, 10)
        self.get_logger().info(
            f"result_writer save={self._save} format={self._format} dir={self._out}"
        )

    def _on(self, msg: GrassSegmentationArray):
        if not self._save:
            return
        image_id = msg.image_id or msg.header.frame_id or "frame"
        segs = segments_to_list(msg)
        payload = {
            "image_id": image_id,
            "header": {
                "stamp": {
                    "sec": int(msg.header.stamp.sec),
                    "nanosec": int(msg.header.stamp.nanosec),
                },
                "frame_id": msg.header.frame_id,
            },
            "segments": segs,
        }
        if self._format in ("json", "both"):
            with open(os.path.join(self._out, "latest_segments.json"), "w") as f:
                json.dump(payload, f, indent=2)
        if self._format in ("annotated", "both"):
            self._save_annotated(image_id, segs)
        self.get_logger().info(f"saved latest output for {image_id} ({len(segs)} segments)")

    def _save_annotated(self, image_id: str, segs: list):
        # Dev: image_id dạng "<file>#<frame>" → đọc lại ảnh gốc trong SAMPLE_DIR để vẽ.
        src = image_id.split("#")[0]
        path = os.path.join(self._sample_dir, src)
        img = cv2.imread(path)
        if img is None:
            self.get_logger().warning(f"annotated skip: cannot read source {path}")
            return
        for s in segs:
            b = s["bbox"]
            x1 = int(b["center_x"] - b["size_x"] / 2)
            y1 = int(b["center_y"] - b["size_y"] / 2)
            x2 = int(b["center_x"] + b["size_x"] / 2)
            y2 = int(b["center_y"] + b["size_y"] / 2)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f'{s["class_name"]}:{s["score"]:.2f}', (x1, max(0, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            points = s["polygon"]["points"]
            if points:
                pts = np.array([[p["x"], p["y"]] for p in points], dtype=np.int32).reshape(-1, 1, 2)
                cv2.polylines(img, [pts], isClosed=True, color=(0, 200, 255), thickness=2)
        cv2.imwrite(os.path.join(self._out, "latest_annotated.jpg"), img)


def main():
    rclpy.init()
    node = ResultWriter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
