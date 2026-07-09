FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
    python3-pip \
    python3-opencv \
    python3-zmq \
    python3-colcon-common-extensions \
    ros-jazzy-cv-bridge \
    ros-jazzy-image-transport \
    ros-jazzy-sensor-msgs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY workspace /workspace

RUN . /opt/ros/jazzy/setup.sh && colcon build

CMD ["bash", "-lc", "source /workspace/install/setup.bash && ros2 launch robot_ai robot_ai.launch.py"]
