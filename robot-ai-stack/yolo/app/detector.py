import rclpy

from rclpy.node import Node

from sensor_msgs.msg import Image
from std_msgs.msg import String

from cv_bridge import CvBridge

from ultralytics import YOLO

import json


class Detector(Node):

    def __init__(self):

        super().__init__(
            "yolo_detector"
        )


        self.bridge = CvBridge()


        self.model = YOLO(
            "/app/models/yolo26n.pt"
        )


        self.subscription = self.create_subscription(
            Image,
            "/camera/image_raw",
            self.callback,
            10
        )


        self.publisher = self.create_publisher(
            String,
            "/yolo/detections",
            10
        )


        self.get_logger().info(
            "YOLO detector ready"
        )


    def callback(
        self,
        msg
    ):


        frame = self.bridge.imgmsg_to_cv2(
            msg,
            "bgr8"
        )


        result = self.model(
            frame,
            verbose=False
        )


        detections=[]


        for r in result:

            for box in r.boxes:

                cls=int(
                    box.cls[0]
                )

                conf=float(
                    box.conf[0]
                )


                detections.append(
                    {
                        "class":self.model.names[cls],
                        "confidence":conf
                    }
                )


        output=String()

        output.data=json.dumps(
            detections
        )


        self.publisher.publish(
            output
        )


        self.get_logger().info(
            str(detections)
        )



def main():

    rclpy.init()

    node=Detector()

    rclpy.spin(node)


    node.destroy_node()

    rclpy.shutdown()



if __name__=="__main__":
    main()
