from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="robot_ai", executable="sample_publisher", name="sample_publisher",
             parameters=[{"mode": "simulate_tiles", "cols": 4, "rows": 3}]),
        Node(package="robot_ai", executable="yolo_bridge", name="yolo_bridge"),
        Node(package="robot_ai", executable="result_writer", name="result_writer"),
    ])
