import json
import os
import re

import cv2
import numpy as np
import rclpy
from rclpy.node import Node

from robot_ai_interfaces.msg import GrassSegmentationArray
from robot_ai.result_format import segments_to_list

_SAFE = re.compile(r"[^A-Za-z0-9._#-]")


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


class ResultWriter(Node):
    """Downstream (tuỳ chọn): lưu kết quả /grass_segments ra file để kiểm/verify.

    MẶC ĐỊNH TẮT — bật bằng env/param để không ghi file khi production.
      RESULT_SAVE=1        bật lưu
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
        stem = _SAFE.sub("_", image_id)
        segs = segments_to_list(msg)
        if self._format in ("json", "both"):
            with open(os.path.join(self._out, stem + ".json"), "w") as f:
                json.dump({"image_id": image_id, "segments": segs}, f, indent=2)
        if self._format in ("annotated", "both"):
            self._save_annotated(image_id, stem, segs)
        self.get_logger().info(f"saved {stem} ({len(segs)} segments)")

    def _save_annotated(self, image_id: str, stem: str, segs: list):
        # Dev: image_id dạng "<file>#<frame>" → đọc lại ảnh gốc trong SAMPLE_DIR để vẽ.
        src = image_id.split("#")[0]
        path = os.path.join(self._sample_dir, src)
        img = cv2.imread(path)
        if img is None:
            self.get_logger().warning(f"annotated skip: cannot read source {path}")
            return
        for s in segs:
            x1, y1, x2, y2 = (int(v) for v in s["bbox_xyxy"])
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f'{s["class_name"]}:{s["score"]:.2f}', (x1, max(0, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            if s["polygon"]:
                pts = np.array(s["polygon"], dtype=np.int32).reshape(-1, 1, 2)
                cv2.polylines(img, [pts], isClosed=True, color=(0, 200, 255), thickness=2)
        cv2.imwrite(os.path.join(self._out, stem + ".jpg"), img)


def main():
    rclpy.init()
    node = ResultWriter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
