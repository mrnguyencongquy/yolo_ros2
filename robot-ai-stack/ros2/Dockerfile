FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
    python3-pip \
    python3-opencv \
    ros-jazzy-cv-bridge \
    ros-jazzy-image-transport \
    ros-jazzy-sensor-msgs \
    ros-jazzy-vision-msgs \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /workspace

COPY workspace /workspace

CMD ["bash"]
