# Changelog

Tất cả thay đổi đáng kể của project ghi ở đây.
Định dạng theo [Keep a Changelog](https://keepachangelog.com/), version theo [SemVer](https://semver.org/).

## [Unreleased]

### Added
- `docs/ARCHITECTURE.md` (living) và `docs/interfaces.md` (integration contract).
- CHANGELOG, CONTRIBUTING, LICENSE, ADR (`docs/adr/`), CI GitHub Actions.
- Truy vết `image_id` ra `/grass_detections` qua `header.frame_id` — **contract 1.1.0**.
- Node tuỳ chọn `result_writer` — lưu `/grass_detections` ra `shared/output/` (JSON + ảnh annotate), env-gated `RESULT_SAVE` (mặc định TẮT), `RESULT_FORMAT=json|annotated|both`.

### Changed
- `Detection2DArray.header.frame_id` giờ mang `image_id` của ảnh gốc (trước là frame_id nguồn).

## [0.1.0] - 2026-07-08

Bản MVP dev-first đầu tiên: pipeline tiling → YOLO → detection theo toạ độ ảnh gốc, chạy trên PC (CUDA), verify E2E.

### Added
- **Tách YOLO khỏi ROS2** qua ZeroMQ REQ/REP; `yolo_server` thuần AI (không rclpy).
- Custom message `robot_ai_interfaces/TileImage`.
- Node `sample_publisher` (đọc folder, chế độ `simulate_tiles`/`passthrough`) và `yolo_bridge` (ZMQ + LOCAL→GLOBAL + aggregate → `vision_msgs/Detection2DArray`).
- Module logic thuần có test: `geometry`, `tiling`, `aggregator`, `detections`, `zmq_client`, `inference` (34 unit test).
- Tách nền tảng bằng Docker Compose override: `docker-compose.pc.yml` (x86 CUDA) / `docker-compose.jetson.yml` (L4T), chọn qua `COMPOSE_FILE` trong `.env`.
- `ros2` image tự build workspace (colcon) + auto-launch pipeline.

### Notes
- Model hiện là COCO (`yolo26n.pt`) để verify luồng; weights cỏ + tiler 4K thật (bên thứ 3) ngoài phạm vi.

[Unreleased]: https://github.com/mrnguyencongquy/yolo_ros2/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mrnguyencongquy/yolo_ros2/releases/tag/v0.1.0
