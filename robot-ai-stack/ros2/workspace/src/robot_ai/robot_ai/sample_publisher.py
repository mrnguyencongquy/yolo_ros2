import os

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node

from robot_ai_interfaces.msg import TileImage
from robot_ai.tiling import split_image

_EXTS = (".jpg", ".jpeg", ".png", ".bmp")


class SamplePublisher(Node):
    """Đọc ảnh trong folder → publish TileImage. Thay tiler bên thứ 3 khi dev."""

    def __init__(self):
        super().__init__("sample_publisher")
        self.declare_parameter("sample_dir", os.environ.get("SAMPLE_DIR", "/images"))
        self.declare_parameter("mode", "simulate_tiles")   # passthrough | simulate_tiles
        self.declare_parameter("cols", 4)
        self.declare_parameter("rows", 3)
        self.declare_parameter("period_s", 2.0)

        self._dir = self.get_parameter("sample_dir").value
        self._mode = self.get_parameter("mode").value
        self._cols = self.get_parameter("cols").value
        self._rows = self.get_parameter("rows").value
        self._bridge = CvBridge()
        self._pub = self.create_publisher(TileImage, "/image_tiles", 10)

        if not os.path.isdir(self._dir):
            self.get_logger().error(f"SAMPLE_DIR not found: {self._dir}")
            raise SystemExit(2)
        self._files = [f for f in sorted(os.listdir(self._dir)) if f.lower().endswith(_EXTS)]
        if not self._files:
            self.get_logger().warning(f"No images in {self._dir}; nothing to publish")
        self._idx = 0
        self.create_timer(self.get_parameter("period_s").value, self._tick)

    def _tick(self):
        if not self._files:
            return
        fname = self._files[self._idx % len(self._files)]
        self._idx += 1
        img = cv2.imread(os.path.join(self._dir, fname))
        if img is None:
            self.get_logger().warning(f"Unreadable image, skipping: {fname}")
            return
        h, w = img.shape[:2]
        if self._mode == "passthrough":
            self._publish_tile(fname, 0, 0, 0, 1, 0, 0, w, h, w, h, img)
        else:
            for spec, tile in split_image(img, self._cols, self._rows):
                self._publish_tile(fname, spec.index, spec.row, spec.col,
                                   self._cols * self._rows, spec.x_offset, spec.y_offset,
                                   spec.width, spec.height, w, h, tile)

    def _publish_tile(self, image_id, index, row, col, num_tiles,
                      x_off, y_off, tw, th, ow, oh, tile_img):
        msg = TileImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "sample"
        msg.image_id = image_id
        msg.tile_index = index
        msg.tile_row = row
        msg.tile_col = col
        msg.num_tiles = num_tiles
        msg.x_offset = x_off
        msg.y_offset = y_off
        msg.tile_width = tw
        msg.tile_height = th
        msg.orig_width = ow
        msg.orig_height = oh
        msg.image = self._bridge.cv2_to_imgmsg(tile_img, encoding="bgr8")
        self._pub.publish(msg)


def main():
    rclpy.init()
    try:
        node = SamplePublisher()
    except SystemExit:
        rclpy.shutdown()
        raise
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
