# Thiết kế: Bản chạy PC (dev-first) + pipeline tiling/toạ độ + tách YOLO khỏi ROS2

- **Ngày:** 2026-07-07
- **Repo:** `git@github.com:mrnguyencongquy/yolo_ros2.git`
- **Trạng thái:** Design đã chốt các quyết định chính, chờ review trước khi qua Test spec → Plan.

## 1. Bối cảnh & mục tiêu

Project `robot-ai-stack` chạy trên **Jetson AGX Orin 64GB** (Ubuntu 24.04, JetPack). Stack Docker Compose 2 service:
- `ros2` — base `ros:jazzy-ros-base` (đa kiến trúc).
- `yolo` — base `dustynv/pytorch:2.7-r36.4.0-cu128-24.04` (**ARM64/L4T, chỉ chạy Jetson**), GPU đặc thù L4T.

**Mục tiêu:**
1. Tạo môi trường chạy trên **PC Ubuntu (x86_64, RTX 3060, nvidia-container-toolkit, Docker 29 / Compose v5)** để **dev & test là chính**; sau khi PC ổn thì tạo bản Jetson để verify. Đồng bộ qua **GitHub (SSH)**.
2. **Tách YOLO khỏi ROS2** (khắc phục việc `detector.py` import `rclpy`/`cv_bridge` mà base image không có ROS2): YOLO thuần AI, giao tiếp qua IPC.
3. Dựng **pipeline nhận ảnh (tile) → detect cỏ → trả bounding box theo toạ độ ảnh gốc 4K** cho ROS2 downstream xử lý.
4. Làm theo **quy trình MVP chuẩn công nghiệp**: design → test spec → plan → code (TDD) → verify.

## 2. Các quyết định đã chốt

| # | Quyết định | Lựa chọn |
|---|---|---|
| 1 | Quản lý khác biệt 2 nền tảng | **Cách A — Docker Compose override files** |
| 2 | Thư mục gốc git repo | **`Grass_Robot/`** (thư mục hiện tại) |
| 3 | Quan hệ YOLO ↔ ROS2 | **Tách rời — YOLO thuần AI, IPC** |
| 4 | Transport IPC | **ZeroMQ (REQ/REP)** |
| 5 | Base image bản PC cho `yolo` | **`pytorch/pytorch:*-cuda12-cudnn9-runtime`** + pip `ultralytics` |
| 6 | Truyền metadata tile qua ROS2 | **Custom msg `TileImage`** (package `robot_ai_interfaces`) |
| 7 | Đầu ra cho ROS2 downstream | **`vision_msgs/Detection2DArray`**, gom 12 tile → 1 msg/ảnh gốc |
| 8 | Node tách tile thật (4K→12) | **Ngoài phạm vi** — do **bên thứ 3** làm. Ta chỉ định **contract** + **sample node đọc ảnh từ folder** để verify luồng |

## 3. Kiến trúc pipeline

Giả định ảnh gốc **4K 3840×2160**, chia **4 cột × 3 hàng = 12 tile** (960×720), **không overlap**. (Chỉnh nếu thực tế khác — logic toạ độ được viết generic nên không phụ thuộc con số này.)

```
[Bên thứ 3: tiler thật]  (NGOÀI phạm vi)
   4K 3840×2160 → 12 tile + metadata offset
        │  publish TileImage lên /image_tiles
        ▼
   ─── (thay thế khi dev bằng) ───▶  [sample_publisher]  đọc ảnh trong folder,
                                      publish TileImage lên /image_tiles
        │
        ▼
[yolo_bridge_node]   (ROS2)
   TileImage.image → cv2 → JPEG ──── ZeroMQ REQ ────▶ [yolo_server]  (thuần AI, KHÔNG ROS2)
                                                        model(tile) → bbox LOCAL + class + score
   nhận detections LOCAL (toạ độ trong tile) ◀──────── ZeroMQ REP :5555
   ── LOCAL→GLOBAL:  gx = x_offset + lx , gy = y_offset + ly  (clamp [0..orig_w/h])
   ── gom theo image_id đến khi đủ num_tiles (hoặc timeout)
        │  publish vision_msgs/Detection2DArray lên /grass_detections
        ▼
[ROS2 downstream]   nhận toàn bộ bbox cỏ (toạ độ 4K gốc) để xử lý
```

**Nguyên tắc thiết kế:**
- `yolo_server` **chỉ trả toạ độ LOCAL** (trong tile) → không cần biết layout → giữ đúng "thuần AI, không ROS2".
- `yolo_bridge` giữ metadata của tile (từ `TileImage` nhận được) và **cộng offset** → toạ độ GLOBAL trên ảnh 4K. ZeroMQ chỉ chở JPEG đi và JSON detections về; **không cần chở metadata** vì bridge đã có sẵn.
- **Gom theo `image_id`**: 12 tile cùng ảnh gốc → **1 `Detection2DArray`/ảnh gốc**.
- **Grass, không phải vegetable**: pipeline coi class generic. Model `.pt` hiện tại là COCO (không có "grass") → cần **weights train riêng cho cỏ**. MVP có thể chạy bằng model COCO để verify luồng, sau đó thay weights cỏ; lọc class mục tiêu qua env `YOLO_TARGET_CLASSES` (tuỳ chọn). *Việc train weights cỏ là dependency ngoài phạm vi code này.*

## 4. Hợp đồng dữ liệu (contract)

### 4.1 `robot_ai_interfaces/msg/TileImage.msg`
```
std_msgs/Header header        # stamp + frame_id nguồn
string image_id               # id ảnh gốc 4K (khoá để gom)
uint16 tile_index             # 0..num_tiles-1
uint16 tile_row
uint16 tile_col
uint16 num_tiles              # tổng số tile của ảnh gốc (biết khi nào gom đủ)
uint32 x_offset               # offset px của tile trong ảnh gốc
uint32 y_offset
uint32 tile_width
uint32 tile_height
uint32 orig_width
uint32 orig_height
sensor_msgs/Image image       # dữ liệu pixel của tile
```

### 4.2 Giao thức ZeroMQ (bridge ⇄ server), REQ/REP
- **Request** (bridge → server): raw bytes = ảnh **JPEG** của tile (`cv2.imencode('.jpg', frame)`).
- **Reply** (server → bridge): UTF-8 **JSON**, list các
  `{"class_id": <int>, "class_name": <str>, "confidence": <float>, "bbox": [x1,y1,x2,y2]}` — **toạ độ LOCAL** trong tile.

### 4.3 Đầu ra `/grass_detections` : `vision_msgs/Detection2DArray`
- `header`: `stamp` + `frame_id` = `image_id` (hoặc frame nguồn).
- Mỗi `Detection2D`:
  - `bbox` (BoundingBox2D): `center` (toạ độ tâm GLOBAL px), `size_x`, `size_y`.
  - `results[0]` (ObjectHypothesisWithPose): `hypothesis.class_id` = tên class, `hypothesis.score` = confidence.

## 5. Tách nền tảng — Compose override (Cách A)

Trong `robot-ai-stack/`:
- `docker-compose.yml` — phần **chung**: 2 service, `network_mode: host`, volumes (`./shared/images`→`/images`, `./models`), env chung (`ROS_DOMAIN_ID`, `YOLO_ZMQ_PORT`, `SAMPLE_DIR`), `depends_on`. Service `yolo` **không** khai báo `dockerfile`/GPU đặc thù (nằm ở override) → **không chạy file base một mình**, luôn kết hợp override.
- `docker-compose.pc.yml`: `yolo` → `build.dockerfile: Dockerfile.pc`, `gpus: all`, env `NVIDIA_VISIBLE_DEVICES=all`/`NVIDIA_DRIVER_CAPABILITIES=all` (KHÔNG `LD_LIBRARY_PATH` L4T).
- `docker-compose.jetson.yml`: `yolo` → `build.dockerfile: Dockerfile.jetson`, `devices: ["nvidia.com/gpu=all"]`, `LD_LIBRARY_PATH=/opt/nvidia/l4t-gpu-libs/nvgpu:/usr/local/cuda/lib64`.
- Mỗi máy: `.env` với `COMPOSE_FILE=docker-compose.yml:docker-compose.pc.yml` (PC) / `...:docker-compose.jetson.yml` (Jetson) → chỉ cần `docker compose up --build`. Commit `env.pc.example`, `env.jetson.example`; **không** commit `.env`.

| | PC (x86) | Jetson (arm64) |
|---|---|---|
| Base `yolo` | `pytorch/pytorch:*-cuda12-cudnn9-runtime` + pip ultralytics | `dustynv/pytorch:...` |
| GPU | `gpus: all` | `devices: ["nvidia.com/gpu=all"]` |
| `LD_LIBRARY_PATH` | (không) | L4T path |

`ultralytics` tự chọn backend theo đuôi file (`.pt`→torch, `.onnx`→onnxruntime, `.engine`→TensorRT); muốn onnx trên PC chỉ thêm `onnxruntime-gpu`.

## 6. Thành phần & cấu trúc repo (MVP chuẩn công nghiệp)

```
Grass_Robot/                                  # git root → github mrnguyencongquy/yolo_ros2
├── README.md · .gitignore
├── docs/
│   ├── specs/2026-07-07-pc-dev-environment-design.md
│   ├── adr/                                  # Architecture Decision Records
│   └── test-spec/                            # sinh ở phase writing-test-specs
├── robot ai stack.txt                        # ghi chú gốc (giữ)
└── robot-ai-stack/
    ├── docker-compose{,.pc,.jetson}.yml · env.pc.example · env.jetson.example
    ├── shared/images/…                       # ảnh sample cho sample_publisher
    ├── models/                               # mount vào yolo
    ├── ros2/
    │   ├── Dockerfile                        # ros:jazzy + pyzmq
    │   └── workspace/src/
    │       ├── robot_ai_interfaces/          # custom msg TileImage (rosidl)
    │       │   ├── msg/TileImage.msg · package.xml · CMakeLists.txt
    │       └── robot_ai/
    │           ├── robot_ai/
    │           │   ├── sample_publisher.py   # đọc folder → publish TileImage
    │           │   └── yolo_bridge.py         # ZeroMQ + LOCAL→GLOBAL + aggregate
    │           ├── launch/robot_ai.launch.py
    │           ├── test/                      # pytest: transform, aggregate, tiling
    │           ├── setup.py · package.xml
    └── yolo/
        ├── Dockerfile.pc · Dockerfile.jetson · requirements.txt
        ├── app/yolo_server.py                # ZeroMQ REP, KHÔNG ROS2
        ├── models/*.pt
        └── tests/                            # pytest: decode, inference wrapper, schema
```

**`sample_publisher.py`** (đứng thay tiler bên thứ 3 khi dev): đọc ảnh trong `SAMPLE_DIR`, publish `TileImage` lên `/image_tiles`. Hai chế độ:
- `passthrough`: mỗi file = 1 tile (offset 0,0, `num_tiles=1`, orig = kích thước ảnh) → verify nhanh luồng analyze→return.
- `simulate_tiles`: tự cắt mỗi ảnh thành 4×3 và publish 12 `TileImage` với offset thật → verify **đầy đủ** luồng tiling + LOCAL→GLOBAL + aggregate ngay khi chưa có bên thứ 3.

## 7. Xử lý lỗi
- **ZeroMQ timeout**: REQ đặt `RCVTIMEO`; quá hạn → log + tái tạo socket (REQ lỗi phải recreate); không chặn ROS2 spin.
- **Thứ tự khởi động**: REQ `connect` chịu được server bind sau (message xếp hàng) → `depends_on` chỉ gợi ý.
- **Load model / GPU fail**: server kiểm `torch.cuda.is_available()`, log thiết bị; lỗi thì exit non-zero.
- **Ảnh hỏng**: server trả `[]` + log, không crash.
- **Aggregate**: buffer theo `image_id`; flush khi đủ `num_tiles` **hoặc** hết `AGG_TIMEOUT` (tile thiếu/trễ); xử lý tile trùng, `image_id` mới tới trước khi cái cũ đủ. Toạ độ global clamp về `[0..orig_w/h]`.

## 8. Chiến lược test (chi tiết hoá ở writing-test-specs)
- **Unit (pytest, thuần hàm)**: LOCAL→GLOBAL transform (kể cả clamp biên); tiling split/merge round-trip (`simulate_tiles`); aggregate theo image_id (đủ/thiếu/trùng/timeout); JPEG encode↔decode; schema JSON detections.
- **ROS2**: `colcon test` / `launch_testing` cho `sample_publisher` + `yolo_bridge`.
- **E2E**: `docker compose up`, sample_publisher (`simulate_tiles`) đẩy ảnh 4K test → assert `/grass_detections` có Detection2DArray toạ độ hợp lệ trong `[0..3840]×[0..2160]`.
- **Lint/format**: `ruff` (python), `ament_lint` (ROS2). (Tuỳ chọn) CI GitHub Actions: build image + `colcon test` + pytest.

## 9. Quy trình MVP theo phase
| Phase | Sản phẩm | Bước |
|---|---|---|
| 0 Design | Spec này + ADR | brainstorming (đang) |
| 1 Test spec | Liệt kê ca test (mục 8) | writing-test-specs |
| 2 Plan | Kế hoạch triển khai từng bước | writing-plans |
| 3 Code | Test trước, code sau | test-driven-development |
| 4 Verify | E2E trên PC (mục 8) | verification |
| 5 Jetson | Verify tương đương | đợt sau |

## 10. Phạm vi
**Trong phạm vi:** git init + `.gitignore` + cấu trúc repo; compose override + env mẫu; `Dockerfile.pc` (mới) + đổi tên Dockerfile hiện tại → `Dockerfile.jetson` + `pyzmq`; `robot_ai_interfaces` (TileImage); `yolo_server.py` (ZeroMQ REP, bỏ ROS2, thay `detector.py`); `sample_publisher.py` (đọc folder, 2 chế độ); `yolo_bridge.py` (ZeroMQ + transform + aggregate → Detection2DArray); launch + setup + Dockerfile ros2 thêm `pyzmq`; unit test + E2E trên PC.

**Ngoài phạm vi (lần này):** tiler thật (bên thứ 3); train weights cỏ; camera thật; overlap tile + NMS xuyên biên; tối ưu throughput/drop-frame; export ONNX/TensorRT; build/tối ưu Jetson (chỉ verify sau); push GitHub remote (chủ máy tự làm bằng chuỗi lệnh git của mình).

## 11. Rủi ro & lưu ý
- **Tag JetPack**: máy báo JetPack 7.2 nhưng image là `r36.4.0` (JetPack 6.x) → khi build `Dockerfile.jetson` phải chọn tag `dustynv/pytorch` khớp JetPack thực tế.
- **Model cỏ**: chưa có weights cỏ → detection thật chưa đúng cho tới khi có; MVP verify luồng bằng COCO.
- **REQ/REP đồng bộ**: throughput giới hạn ở tốc độ inference; cần drop-frame/parallel thì đổi pattern sau (ngoài phạm vi).
- **Kích thước image PC** (`pytorch/pytorch`+cuda) vài GB — bình thường.
