# Architecture — yolo_ros2 grass-detection stack

> Living document mô tả **hệ thống hiện tại**. Lịch sử thiết kế/lý do xem `docs/superpowers/specs/` và `docs/adr/`. Hợp đồng tích hợp chi tiết xem [`interfaces.md`](interfaces.md).

## 1. Tổng quan

Pipeline nhận **tile** của ảnh 4K, chạy YOLO detect trên từng tile, ánh xạ bbox về toạ độ ảnh gốc và gom lại thành kết quả cho mỗi ảnh gốc. Chạy **dev-first trên PC x86 (CUDA)**, verify trên **Jetson**; khác biệt nền tảng cô lập bằng Docker Compose override.

```
[bên thứ 3: tiler]  (production)                     ┌─ container: ros2 (ROS2 Jazzy) ─────────────┐
  4K → 12 tile + metadata ──publish TileImage──▶      │  sample_publisher (dev stand-in)           │
        (khi dev: sample_publisher đứng thay)          │  yolo_bridge                                │
                                                       └──────────────┬──────────────────────────────┘
  /image_tiles (TileImage)  ──────────────────────────────────────────┘
        │ (yolo_bridge subscribe)
        ▼
  yolo_bridge ── JPEG bytes / ZeroMQ REQ ──▶ ┌─ container: yolo (KHÔNG ROS2) ─┐
                                             │  yolo_server (ZMQ REP :5555)    │
  bbox LOCAL / JSON ◀── ZeroMQ REP ──────────│  YOLO inference (GPU)           │
        │                                    └────────────────────────────────┘
        │ LOCAL→GLOBAL + gom 12 tile theo image_id
        ▼
  /grass_detections (vision_msgs/Detection2DArray, toạ độ ảnh gốc)
        │
        ▼  [ROS2 downstream: điều hướng / xử lý]
```

## 2. Thành phần

| Thành phần | Container | ROS2? | Trách nhiệm | Code |
|---|---|---|---|---|
| `sample_publisher` | ros2 | ✅ node | Đọc ảnh folder → cắt 4×3 tile → publish `TileImage`. **Chỉ dùng khi dev** (thay tiler bên thứ 3). | `robot_ai/sample_publisher.py` |
| `yolo_bridge` | ros2 | ✅ node | Cầu nối ROS2↔YOLO + **xử lý**: JPEG-encode, gọi ZMQ, đổi LOCAL→GLOBAL, gom theo `image_id`, publish `Detection2DArray`. | `robot_ai/yolo_bridge.py` |
| `yolo_server` | yolo | ❌ thuần ZMQ | Load model, ZMQ REP, inference từng tile, trả bbox LOCAL. **Không biết ROS2/toạ độ gốc.** | `yolo/app/yolo_server.py` |
| `robot_ai_interfaces` | (build) | — | Định nghĩa msg `TileImage`. | `.../robot_ai_interfaces/msg/TileImage.msg` |

**Module logic thuần** (không phụ thuộc ROS2 → test bằng pytest trên host):

| Module | Nhiệm vụ | Test |
|---|---|---|
| `geometry.py` | `local_to_global` + clamp bbox | `test_geometry.py` |
| `tiling.py` | `compute_tiles` / `split_image` (grid 4×3, phần dư dồn tile cuối) | `test_tiling.py` |
| `aggregator.py` | `DetectionAggregator` — gom theo `image_id`, timeout flush, dedup | `test_aggregator.py` |
| `detections.py` | `parse_detections` — parse reply JSON, bỏ record hỏng | `test_detections.py` |
| `zmq_client.py` | `ZmqReqClient` — REQ + recreate-on-timeout | `test_zmq_client.py` |
| `detection_msg.py` | build `vision_msgs/Detection2DArray` | (colcon/E2E) |
| `yolo/app/inference.py` | `decode_jpeg` + `run_inference` | `test_inference.py` |

## 3. Luồng dữ liệu (end-to-end)

1. Nguồn publish 12 `TileImage`/ảnh gốc lên `/image_tiles` (mỗi tile kèm offset + `num_tiles` + `image_id`).
2. `yolo_bridge` mỗi tile: `cv_bridge` → cv2 → `imencode('.jpg')` → ZMQ REQ tới `tcp://127.0.0.1:5555`.
3. `yolo_server`: `imdecode` → `model(tile)` (GPU) → JSON list bbox **LOCAL** → REP.
4. `yolo_bridge`: `parse_detections` → `local_to_global` (cộng `x_offset/y_offset`, clamp `[0..orig]`) → `DetectionAggregator.add(image_id, ...)`.
5. Khi đủ `num_tiles` (hoặc timeout) → build `Detection2DArray` (toạ độ ảnh gốc) → publish `/grass_detections`.

## 4. Triển khai

- **Compose**: `docker-compose.yml` (chung) + override `docker-compose.pc.yml` (base `pytorch/pytorch` CUDA + `gpus: all`) hoặc `docker-compose.jetson.yml` (base `dustynv/pytorch` L4T + `nvidia.com/gpu`). Chọn qua `COMPOSE_FILE` trong `.env`.
- **Mạng**: cả 2 container `network_mode: host` → ZMQ qua `127.0.0.1:5555`, hoạt động giống nhau trên PC/Jetson.
- **GPU**: PC dùng `gpus: all`; Jetson dùng CDI `nvidia.com/gpu=all` + `LD_LIBRARY_PATH` L4T.
- **ros2 image**: cài `colcon`, build workspace trong image, CMD auto-launch `robot_ai.launch.py`.

## 5. Nguyên tắc thiết kế

- **YOLO tách rời ROS2** (giao tiếp ZMQ) → không xung đột `cv_bridge`, đổi model tự do. Xem ADR ZeroMQ.
- **Logic thuần tách khỏi node** → test nhanh không cần ROS2/Docker.
- **Nền tảng tách bằng compose override**, không đụng code.
- **`yolo_server` "ngu"** (chỉ trả LOCAL) — mọi tri thức về layout tile nằm ở `yolo_bridge`.

## 6. Tech stack

ROS2 Jazzy · Docker Compose · ZeroMQ (pyzmq) · Ultralytics YOLO · PyTorch CUDA · OpenCV · vision_msgs · pytest/colcon.

## 7. Ngoài phạm vi hiện tại / roadmap

- Weights train riêng cho **cỏ** (đang dùng COCO để verify luồng).
- Tiler 4K thật (bên thứ 3) — contract `TileImage` đã sẵn sàng.
- Overlap tile + NMS xuyên biên; throughput/parallel (REQ/REP hiện lockstep).
- Export ONNX/TensorRT; build/tối ưu Jetson.
- **Propagate `image_id` ra `Detection2DArray`** (hiện `header.frame_id` mang frame_id nguồn, `image_id` chỉ dùng nội bộ để gom) — xem `interfaces.md`.
