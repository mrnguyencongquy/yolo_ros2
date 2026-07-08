import os
import subprocess
import sys


def test_invalid_port_exits_nonzero():         # TC-09
    env = dict(os.environ, YOLO_ZMQ_PORT="abc", YOLO_MODEL="/nonexistent.pt")
    p = subprocess.run([sys.executable, "app/yolo_server.py"], env=env,
                       capture_output=True, text=True, cwd=os.getcwd())
    assert p.returncode == 2
    assert "YOLO_ZMQ_PORT" in p.stderr


def test_missing_model_exits_nonzero():        # TC-40
    env = dict(os.environ, YOLO_ZMQ_PORT="5555", YOLO_MODEL="/nonexistent.pt")
    p = subprocess.run([sys.executable, "app/yolo_server.py"], env=env,
                       capture_output=True, text=True, cwd=os.getcwd())
    assert p.returncode == 3
    assert "model not found" in p.stderr


def test_module_imports_without_ros2():        # TC-48
    with open("app/yolo_server.py") as f:
        src = f.read()
    assert "rclpy" not in src and "cv_bridge" not in src
