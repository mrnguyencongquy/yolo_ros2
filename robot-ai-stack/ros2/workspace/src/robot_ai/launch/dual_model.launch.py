import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

from robot_ai.runtime_paths import model_output_dir, model_output_topic


def generate_launch_description():
    base_model = os.environ.get("YOLO_BASE_MODEL", "/models/yolo11n.pt")
    trained_model = os.environ.get("YOLO_TRAINED_MODEL", "/models/yolo26n-seg.pt")
    base_topic = model_output_topic(base_model)
    trained_topic = model_output_topic(trained_model)
    base_port = LaunchConfiguration("base_zmq_port")
    trained_port = LaunchConfiguration("trained_zmq_port")
    sample_period = LaunchConfiguration("sample_period_s")
    watch_new_files = LaunchConfiguration("watch_new_files")

    return LaunchDescription([
        DeclareLaunchArgument("base_zmq_port", default_value="5555"),
        DeclareLaunchArgument("trained_zmq_port", default_value="5556"),
        DeclareLaunchArgument("sample_period_s", default_value="0.2"),
        DeclareLaunchArgument("watch_new_files", default_value="false"),
        Node(
            package="robot_ai",
            executable="sample_publisher",
            name="sample_publisher",
            parameters=[{
                "mode": "simulate_tiles",
                "cols": 4,
                "rows": 3,
                "period_s": ParameterValue(sample_period, value_type=float),
                "watch_new_files": ParameterValue(watch_new_files, value_type=bool),
            }],
        ),
        Node(
            package="robot_ai",
            executable="yolo_bridge",
            name="yolo_bridge_base",
            parameters=[{
                "zmq_port": ParameterValue(base_port, value_type=int),
                "output_topic": base_topic,
            }],
        ),
        Node(
            package="robot_ai",
            executable="yolo_bridge",
            name="yolo_bridge_trained",
            parameters=[{
                "zmq_port": ParameterValue(trained_port, value_type=int),
                "output_topic": trained_topic,
            }],
        ),
        Node(
            package="robot_ai",
            executable="result_writer",
            name="result_writer_base",
            parameters=[{
                "input_topic": base_topic,
                "out_dir": model_output_dir(base_model),
            }],
        ),
        Node(
            package="robot_ai",
            executable="result_writer",
            name="result_writer_trained",
            parameters=[{
                "input_topic": trained_topic,
                "out_dir": model_output_dir(trained_model),
            }],
        ),
    ])
