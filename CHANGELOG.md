# Changelog

Tất cả thay đổi đáng kể của project ghi ở đây.
Định dạng theo [Keep a Changelog](https://keepachangelog.com/), version theo [SemVer](https://semver.org/).

## [Unreleased]

### Added
- `docs/ARCHITECTURE.md` (living) và `docs/interfaces.md` (integration contract).
- CHANGELOG, CONTRIBUTING, LICENSE, ADR (`docs/adr/`), CI GitHub Actions.
- Truy vết `image_id` ra `/grass_detections` qua `header.frame_id` — **contract 1.1.0**.
- Custom segmentation output `/grass_segments` với `GrassSegmentationArray/GrassSegment` — **contract 1.2.0**.
- Node `result_writer` — ghi đè output mới nhất của `/grass_segments` vào `shared/output/latest_segments.json` và `latest_annotated.jpg`, `RESULT_FORMAT=json|annotated|both`.
- Bỏ field `mask` khỏi `GrassSegment`; output chính còn `class_name`, `score`, `bbox`, `polygon.points`.

### Removed
- Topic tương thích `/grass_detections` (`vision_msgs/Detection2DArray`) — **contract 2.0.0**; `/grass_segments` là output DUY NHẤT. Bỏ `vision_msgs` khỏi deps.

### Fixed
- Cô lập ROS2 discovery về `LOCALHOST` (`ROS_AUTOMATIC_DISCOVERY_RANGE`) cho container `ros2` — tránh merge nhầm graph với node ROS2 khác trên LAN (vd Jetson cùng `ROS_DOMAIN_ID=0`) khiến `yolo_bridge` nhận tile/ảnh cũ + node bị trùng.

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
