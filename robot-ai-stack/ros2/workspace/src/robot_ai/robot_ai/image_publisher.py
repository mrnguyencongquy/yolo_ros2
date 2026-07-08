import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from cv_bridge import CvBridge

import cv2
import os
import time


class ImagePublisher(Node):

    def __init__(self):

        super().__init__(
            "image_publisher"
        )

        self.publisher = self.create_publisher(
            Image,
            "/camera/image_raw",
            10
        )

        self.bridge = CvBridge()


        self.image_dir = "/shared/images"


        self.images = sorted(
            [
                os.path.join(
                    self.image_dir,
                    x
                )
                for x in os.listdir(self.image_dir)
                if x.endswith(
                    (".jpg",".png",".jpeg")
                )
            ]
        )


        self.index = 0


        self.timer = self.create_timer(
            1.0,
            self.publish_image
        )


        self.get_logger().info(
            f"Found {len(self.images)} images"
        )


    def publish_image(self):

        if not self.images:
            return


        img_path = self.images[self.index]


        frame = cv2.imread(
            img_path
        )


        if frame is None:
            return


        msg = self.bridge.cv2_to_imgmsg(
            frame,
            encoding="bgr8"
        )


        msg.header.frame_id="camera"


        self.publisher.publish(
            msg
        )


        self.get_logger().info(
            f"Published {img_path}"
        )


        self.index += 1


        if self.index >= len(self.images):
            self.index = 0



def main():

    rclpy.init()

    node = ImagePublisher()

    rclpy.spin(node)

    node.destroy_node()

    rclpy.shutdown()


if __name__=="__main__":
    main()
