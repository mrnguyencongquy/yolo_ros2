import re

import pytest

from robot_ai.runtime_paths import model_identifier, model_output_dir, model_output_topic

# ROS 2 topic names only allow alphanumerics, '_' and '/' (rclpy validate_topic_name),
# so the identifier must never contain '-' or '.'.
ROS_TOPIC_RE = re.compile(r"^/[A-Za-z0-9_/]+$")


def test_uses_model_filename_stem():
    assert model_output_dir("/models/yolo26s_trained-v4.pt") == "/output/yolo26s_trained_v4"


def test_sanitizes_model_filename():
    assert model_output_dir("/models/yolo trained (v4).pt") == "/output/yolo_trained_v4"


def test_hyphen_and_dot_become_underscore():
    assert model_identifier("/models/yolo26n-seg.pt") == "yolo26n_seg"
    assert model_identifier("/models/best.v2-final.pt") == "best_v2_final"


def test_uses_model_filename_for_output_topic():
    assert model_output_topic("/models/yolo26n-seg.pt") == "/models/yolo26n_seg/detected_instances"


def test_output_topic_is_ros_safe():
    for path in ("/models/yolo26n-seg.pt", "/models/yolo v8 (custom).pt", "/models/a.b-c.pt"):
        assert ROS_TOPIC_RE.match(model_output_topic(path))


def test_rejects_path_without_filename():
    with pytest.raises(ValueError):
        model_output_dir("/")
