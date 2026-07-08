# Architecture — yolo_ros2 grass-detection stack

> Living document mô tả **hệ thống hiện tại**. Lịch sử thiết kế/lý do xem `docs/superpowers/specs/` và `docs/adr/`. Hợp đồng tích hợp chi tiết xem [`interfaces.md`](interfaces.md). Workflow input/output/metadata chi tiết xem [`workflow.md`](workflow.md).

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

## 3. Chế độ vận hành

### 3.1 Dev / test mode

Hiện tại Docker launch chạy `sample_publisher` cùng `yolo_bridge`.

```text
shared/images/*.jpg
  -> sample_publisher
  -> tự chia 4x3 tile + tạo metadata TileImage
  -> /image_tiles
  -> yolo_bridge
  -> yolo_server
  -> /grass_detections
```

`sample_publisher` là stand-in cho tiler bên thứ 3. Node này đọc ảnh gốc trong folder, tự chia tile, tự điền `image_id`, `tile_index`, `x_offset`, `y_offset`, `orig_width`, `orig_height`.

### 3.2 Production mode

Trong production, tiler bên thứ 3 thay `sample_publisher`.

```text
bên thứ 3 / tiler thật
  -> ảnh 4K
  -> 12 tile + metadata
  -> publish TileImage lên /image_tiles
  -> yolo_bridge
  -> yolo_server
  -> /grass_detections
```

Khi tích hợp production, `yolo_bridge` không cần biết tile đến từ file hay camera. Điều kiện duy nhất là publisher phải tuân thủ contract `robot_ai_interfaces/msg/TileImage`.

## 4. Luồng dữ liệu (end-to-end)

### 4.1 Input ROS2: `/image_tiles`

Nguồn publish `TileImage` lên `/image_tiles`:

- Dev: `sample_publisher`
- Production: tiler bên thứ 3

Mỗi ảnh gốc tạo `num_tiles` message. Ví dụ ảnh 4K chia 4x3 thì publish 12 message có cùng `image_id`.

Metadata quan trọng:

| Metadata | Nhiệm vụ |
|---|---|
| `image_id` | khóa gom tile cùng ảnh gốc |
| `tile_index` | dedup tile, biết tile nào đã nhận |
| `num_tiles` | biết khi nào gom đủ để emit output |
| `x_offset`, `y_offset` | đổi bbox local trong tile thành bbox global trên ảnh gốc |
| `orig_width`, `orig_height` | clamp bbox không vượt biên ảnh |
| `image` | pixel tile để gửi cho YOLO |

### 4.2 Bridge ROS2 -> YOLO

Với mỗi tile, `yolo_bridge` xử lý:

1. Subscribe `TileImage` từ `/image_tiles`.
2. Convert `sensor_msgs/Image` sang OpenCV image.
3. Encode tile thành JPEG bytes.
4. Gửi JPEG bytes qua ZeroMQ REQ tới `tcp://127.0.0.1:${YOLO_ZMQ_PORT}`.

Metadata không gửi sang `yolo_server`; bridge giữ metadata để map kết quả sau khi YOLO trả về.

### 4.3 YOLO inference

`yolo_server` không dùng ROS2. Nó chỉ nhận JPEG bytes, chạy model, trả JSON detection:

```json
[
  {
    "class_id": 0,
    "class_name": "person",
    "confidence": 0.87,
    "bbox": [10.0, 20.0, 50.0, 60.0]
  }
]
```

`bbox` do YOLO trả là **LOCAL** trong tile.

### 4.4 Bridge YOLO -> ROS2 output

`yolo_bridge` nhận JSON và xử lý:

1. Parse detection JSON.
2. Đổi bbox LOCAL sang GLOBAL:
   ```text
   global_x = x_offset + local_x
   global_y = y_offset + local_y
   ```
3. Clamp bbox vào `[0..orig_width] x [0..orig_height]`.
4. Gom detection theo `image_id` bằng `DetectionAggregator`.
5. Khi đủ `num_tiles` hoặc timeout, build `vision_msgs/Detection2DArray`.
6. Publish output lên `/grass_detections`.

### 4.5 Output ROS2: `/grass_detections`

`/grass_detections` là output cho downstream. Repo hiện tại chưa có node downstream riêng; có thể inspect bằng:

```bash
ros2 topic echo /grass_detections
```

Mỗi detection chứa:

| Field | Ý nghĩa |
|---|---|
| `header.frame_id` | ảnh/frame sinh ra detection |
| `results[0].hypothesis.class_id` | tên class YOLO detect được |
| `results[0].hypothesis.score` | confidence |
| `bbox.center.position.x/y` | tâm bbox trên ảnh gốc |
| `bbox.size_x/size_y` | kích thước bbox trên ảnh gốc |

Downstream có thể dùng output này để vẽ bbox, log JSON, điều hướng, hoặc xử lý điều khiển robot.

## 5. Triển khai

- **Compose**: `docker-compose.yml` (chung) + override `docker-compose.pc.yml` (base `pytorch/pytorch` CUDA + `gpus: all`) hoặc `docker-compose.jetson.yml` (base `dustynv/pytorch` L4T + `nvidia.com/gpu`). Chọn qua `COMPOSE_FILE` trong `.env`.
- **Mạng**: cả 2 container `network_mode: host` → ZMQ qua `127.0.0.1:5555`, hoạt động giống nhau trên PC/Jetson.
- **GPU**: PC dùng `gpus: all`; Jetson dùng CDI `nvidia.com/gpu=all` + `LD_LIBRARY_PATH` L4T.
- **ros2 image**: cài `colcon`, build workspace trong image, CMD auto-launch `robot_ai.launch.py`.

## 6. Nguyên tắc thiết kế

- **YOLO tách rời ROS2** (giao tiếp ZMQ) → không xung đột `cv_bridge`, đổi model tự do. Xem ADR ZeroMQ.
- **Logic thuần tách khỏi node** → test nhanh không cần ROS2/Docker.
- **Nền tảng tách bằng compose override**, không đụng code.
- **`yolo_server` "ngu"** (chỉ trả LOCAL) — mọi tri thức về layout tile nằm ở `yolo_bridge`.

## 7. Tech stack

ROS2 Jazzy · Docker Compose · ZeroMQ (pyzmq) · Ultralytics YOLO · PyTorch CUDA · OpenCV · vision_msgs · pytest/colcon.

## 8. Ngoài phạm vi hiện tại / roadmap

- Weights train riêng cho **cỏ** (đang dùng COCO để verify luồng).
- Tiler 4K thật (bên thứ 3) — contract `TileImage` đã sẵn sàng.
- Overlap tile + NMS xuyên biên; throughput/parallel (REQ/REP hiện lockstep).
- Export ONNX/TensorRT; build/tối ưu Jetson.
