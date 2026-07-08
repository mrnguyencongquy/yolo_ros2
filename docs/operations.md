# Operations Runbook

Tài liệu này gom các lệnh vận hành thường dùng cho stack ROS2 + YOLO: setup môi trường, chạy Docker, kiểm tra topic/log/progress, test, và thao tác git cơ bản.

## 1. Chọn Nền Tảng

Từ root repo:

```bash
cd robot-ai-stack
```

PC CUDA:

```bash
cp env.pc.example .env
```

Jetson:

```bash
cp env.jetson.example .env
```

Kiểm tra compose sau khi chọn `.env`:

```bash
docker compose config
```

Nếu không dùng `.env`, chỉ định tường minh:

```bash
docker compose -f docker-compose.yml -f docker-compose.pc.yml config
docker compose -f docker-compose.yml -f docker-compose.jetson.yml config
```

## 2. Build Và Chạy Docker

Chạy foreground để xem log trực tiếp:

```bash
docker compose up --build
```

Chạy nền:

```bash
docker compose up -d --build
```

Kiểm tra container:

```bash
docker compose ps
```

Restart:

```bash
docker compose restart
```

Dừng và xóa container:

```bash
docker compose down
```

Rebuild không cache khi nghi ngờ image cũ:

```bash
docker compose build --no-cache
docker compose up -d
```

## 3. Kiểm Tra Log

Log YOLO server:

```bash
docker compose logs -f yolo
```

Cần thấy các dòng kiểu:

```text
[yolo_server] device=cuda model=/app/models/yolo26n.pt
[yolo_server] listening on tcp://*:5555
```

Log ROS2 pipeline:

```bash
docker compose logs -f ros2
```

Cần thấy các dòng kiểu:

```text
yolo_bridge -> tcp://127.0.0.1:5555
published N dets for image_id=<file>#<frame>
```

Ý nghĩa:

- `published N dets`: bridge đã gom xong các tile của một ảnh gốc và publish output.
- `image_id=<file>#<frame>`: frame cụ thể đã xử lý.
- `N=0` vẫn hợp lệ nếu YOLO không detect object.

## 4. Vào Container ROS2

```bash
docker compose exec ros2 bash
```

Trong container, source environment:

```bash
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash
```

Kiểm tra `ros2`:

```bash
which ros2
ros2 node list
ros2 topic list
```

## 5. Kiểm Tra Topic Và Progress

Xem publisher/subscriber:

```bash
ros2 topic info /image_tiles -v
ros2 topic info /grass_detections -v
```

Xem một input tile:

```bash
ros2 topic echo /image_tiles --once
```

Xem output detection:

```bash
ros2 topic echo /grass_detections
```

Xem tần suất:

```bash
ros2 topic hz /image_tiles
ros2 topic hz /grass_detections
```

Nếu `/image_tiles` có data nhưng `/grass_detections` không có:

```bash
docker compose logs --tail=100 ros2
docker compose logs --tail=100 yolo
```

Các nguyên nhân thường gặp:

- `yolo` chưa listening port `5555`.
- `YOLO_ZMQ_PORT` giữa 2 service không khớp.
- `SAMPLE_DIR` không có ảnh.
- YOLO timeout, bridge log `yolo_server timeout`.

## 6. Kiểm Tra Dữ Liệu Mẫu

Ảnh dev được mount vào container ROS2 từ:

```text
robot-ai-stack/shared/images -> /images
```

Kiểm tra trên host:

```bash
ls -lh shared/images
```

Kiểm tra trong container:

```bash
docker compose exec ros2 bash -lc "ls -lh /images"
```

Hiện `sample_publisher` dùng ảnh trong folder này để mô phỏng tiler bên thứ 3. Production sẽ thay bằng publisher thật lên `/image_tiles`.

## 7. Chạy Test

ROS2 build:

```bash
cd robot-ai-stack/ros2/workspace
colcon build
source install/setup.bash
```

Unit test ROS2 package bằng pytest trực tiếp:

```bash
cd robot-ai-stack/ros2/workspace/src/robot_ai
/usr/bin/python3 -m pytest -q
```

YOLO unit test:

```bash
cd robot-ai-stack/yolo
/usr/bin/python3 -m pytest -q tests
```

Ghi chú: `colcon test` hiện cần cấu hình pytest đúng trong package Python; nếu thấy `Ran 0 tests / NO TESTS RAN`, đó là runner issue chứ không phải test logic pass.

## 8. Git Workflow Cơ Bản

Xem trạng thái:

```bash
git status --short
```

Xem diff:

```bash
git diff
git diff --staged
```

Stage file có chủ đích:

```bash
git add docs/ARCHITECTURE.md docs/interfaces.md docs/workflow.md docs/operations.md
git add robot-ai-stack/ros2/workspace/src/robot_ai/robot_ai/yolo_bridge.py
```

Commit:

```bash
git commit -m "docs: add workflow and operations runbook"
```

Xem lịch sử:

```bash
git log --oneline -10
```

Không commit các folder runtime:

```text
build/
install/
log/
__pycache__/
.pytest_cache/
```

Không commit dữ liệu capture/model mới trừ khi có chủ ý:

```text
robot-ai-stack/shared/images/*
robot-ai-stack/yolo/models/*.pt
robot-ai-stack/yolo/models/*.onnx
robot-ai-stack/yolo/models/*.engine
```

Nếu thật sự muốn version một file đang bị ignore:

```bash
git add -f path/to/file
```

## 9. Docker Context Và Ignore

ROS2 build context dùng:

```text
robot-ai-stack/ros2/.dockerignore
```

YOLO build context dùng:

```text
robot-ai-stack/yolo/.dockerignore
```

Các file nên bị loại khỏi Docker context:

- `build/`, `install/`, `log/`
- `__pycache__/`, `.pytest_cache/`
- test output, local log

Không ignore `yolo/models/*.pt` trong Docker context hiện tại vì Dockerfile đang `COPY models ./models` để container có model bootstrap.

## 10. Cleanup

Dừng container:

```bash
docker compose down
```

Xóa image build lại từ đầu:

```bash
docker compose down
docker compose build --no-cache
```

Xóa cache colcon trên host nếu cần build sạch:

```bash
rm -rf robot-ai-stack/ros2/workspace/build robot-ai-stack/ros2/workspace/install robot-ai-stack/ros2/workspace/log
```

Chỉ dùng cleanup Docker toàn hệ thống khi hiểu tác động vì có thể xóa image/cache của project khác.
