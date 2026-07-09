# yolo_ros2 — Grass detection AI stack

ROS2 Jazzy + YOLO (Ultralytics) tiling detection pipeline. Dev trên **PC x86 (CUDA)**, verify trên **Jetson**.

## Kiến trúc (tóm tắt)

```
[sample_publisher]  đọc ảnh trong folder → cắt 4×3 tile → publish TileImage lên /image_tiles
        │                (thay tiler thật của bên thứ 3 khi dev)
        ▼
[yolo_bridge]  tile → JPEG ── ZeroMQ REQ ──▶ [yolo_server]  (thuần AI, KHÔNG ROS2)
                                               model(tile) → bbox LOCAL + class + score
   nhận bbox LOCAL ◀──── ZeroMQ REP :5555 ─────┘
   ── LOCAL→GLOBAL (cộng offset tile) + gom 12 tile theo image_id
        │
        ▼  /grass_segments  (GrassSegmentationArray, toạ độ ảnh gốc 4K)
[ROS2 downstream]
```

- 2 container: `ros2` (Jazzy, chạy `sample_publisher` + `yolo_bridge`) và `yolo` (YOLO server).
- Khác biệt nền tảng nằm ở compose override: `docker-compose.pc.yml` (base CUDA x86) vs `docker-compose.jetson.yml` (base L4T).

## Yêu cầu

**PC (dev):** Docker + Docker Compose v2/v5, NVIDIA GPU + driver + `nvidia-container-toolkit`.
**Jetson (verify):** JetPack tương ứng + `nvidia-container-toolkit`.
**Dev/test không Docker (tuỳ chọn):** ROS2 Jazzy + `colcon`, Python 3.12 (`pytest numpy opencv-python pyzmq`).

## Chạy nhanh

Chọn nền tảng bằng cách copy file env tương ứng thành `.env` (khai báo `COMPOSE_FILE`):

```bash
cd robot-ai-stack

# PC
cp env.pc.example .env
docker compose up --build

# Jetson
cp env.jetson.example .env
docker compose up --build
```

> Đã có `.env` thì chỉ cần `docker compose up --build`. Không dùng `.env` thì chỉ định tường minh:
> `docker compose -f docker-compose.yml -f docker-compose.pc.yml up --build`

Khi chạy sẽ thấy:
- `yolo`: `[yolo_server] device=cuda ...` + `listening on tcp://*:5555`.
- `ros2`: `published N segments for image_id=<file>#<frame>` — mỗi dòng là 1 ảnh gốc đã xử lý & publish lên `/grass_segments`.

## Xem kết quả & thao tác thường dùng

```bash
# Xem message detection (mở terminal khác)
docker compose exec ros2 bash -lc \
  "source /opt/ros/jazzy/setup.bash && source /workspace/install/setup.bash && ros2 topic echo /grass_segments"

# Xem log
docker compose logs -f yolo      # server (device, listening, lỗi)
docker compose logs -f ros2      # bridge/publisher (published N dets ...)

# Chạy nền / dừng
docker compose up -d --build     # detached
docker compose down              # dừng & xoá container
```

**Đọc log "published N dets for image_id=test.jpg#179":** bridge đã gom đủ 12 tile của 1 ảnh gốc (frame #179) và publish `N` detection. `#N` là frame counter (mỗi vòng đọc lại file là 1 frame mới) nên pipeline phát liên tục.

## Cấu hình (biến môi trường)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `YOLO_ZMQ_PORT` | `5555` | Cổng ZeroMQ giữa bridge và server (dùng chung 2 service) |
| `YOLO_MODEL` | `/app/models/yolo26n.pt` | Đường dẫn model trong container `yolo` (đổi sang weights cỏ khi có) |
| `YOLO_TARGET_CLASSES` | (rỗng) | Lọc class, phân tách bằng dấu phẩy, vd `grass`. Rỗng = trả tất cả |
| `SAMPLE_DIR` | `/images` | Thư mục ảnh sample (mount từ `shared/images`) |
| `ROS_DOMAIN_ID` | `0` | ROS2 domain |

Tham số node `sample_publisher` (trong `launch/robot_ai.launch.py`): `mode` (`simulate_tiles` | `passthrough`), `cols` (4), `rows` (3), `period_s` (2.0).

## Dev & test không cần Docker (chạy trên host)

```bash
# Unit test (logic thuần: transform toạ độ, tiling, aggregate, parser, zmq client)
cd robot-ai-stack/ros2/workspace/src/robot_ai && python3 -m pytest test/ -v
cd robot-ai-stack/yolo && python3 -m pytest tests/ -v

# Build + source workspace ROS2
cd robot-ai-stack/ros2/workspace
colcon build
source install/setup.bash
```

## Ghi chú

- Model hiện tại là **COCO** (`yolo26n.pt`) — dùng để verify luồng. Detect **cỏ** cần weights train riêng, thay qua `YOLO_MODEL` (+ `YOLO_TARGET_CLASSES=grass` nếu muốn lọc).
- Node cắt tile 4K→12 thật do **bên thứ 3** publish `TileImage` lên `/image_tiles`; `sample_publisher` chỉ đứng thay khi dev.
- Bản Jetson: kiểm tra tag `dustynv/pytorch` trong `yolo/Dockerfile.jetson` khớp JetPack thực tế trên máy.

## Push lên GitHub

```bash
git remote add origin git@github.com:mrnguyencongquy/yolo_ros2.git
git push -u origin main
```

## Tài liệu

- **Kiến trúc (living):** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Hợp đồng tích hợp:** [`docs/interfaces.md`](docs/interfaces.md) — TileImage, topics, ZMQ, env (bên thứ 3 & downstream đọc file này)
- **Workflow input/output/metadata:** [`docs/workflow.md`](docs/workflow.md)
- **Vận hành / runbook:** [`docs/operations.md`](docs/operations.md)
- Thiết kế (lịch sử): `docs/superpowers/specs/`
- Test spec: `docs/superpowers/test-specs/`
- Kế hoạch triển khai: `docs/superpowers/plans/`
