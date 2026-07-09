# Interfaces / Integration Contract — yolo_ros2

> Hợp đồng tích hợp giữa các bên. **Bên thứ 3** (tiler) publish vào `/image_tiles`; **downstream** consume `/grass_segments`. Thay đổi contract phải bump version (mục cuối) và ghi `CHANGELOG`.

**Contract version:** `2.0.0`

---

## 1. Input topic — `/image_tiles`

- **Type:** `robot_ai_interfaces/msg/TileImage`
- **Publisher:** tiler bên thứ 3 (production) hoặc `sample_publisher` (dev)
- **Subscriber:** `yolo_bridge`
- **QoS:** default (reliable, depth 10)
- **Ngữ nghĩa:** mỗi ảnh gốc được chia thành `num_tiles` tile; publish lần lượt từng tile (thứ tự tuỳ ý — bridge gom theo `image_id`).

### `TileImage.msg`
| Field | Type | Ý nghĩa | Ràng buộc |
|---|---|---|---|
| `header` | `std_msgs/Header` | `stamp` + `frame_id` nguồn | — |
| `image_id` | `string` | **Khoá gom** — id ảnh gốc; **phải DUY NHẤT mỗi frame** | non-empty; khác nhau giữa các frame |
| `tile_index` | `uint16` | Chỉ số tile trong ảnh gốc | `0 .. num_tiles-1`, duy nhất trong cùng `image_id` |
| `tile_row` / `tile_col` | `uint16` | Vị trí lưới (thông tin) | — |
| `num_tiles` | `uint16` | Tổng số tile của ảnh gốc | `> 0` (0 sẽ bị bỏ) |
| `x_offset` / `y_offset` | `uint32` | Offset px của tile trong ảnh gốc | `0 .. orig_w/orig_h` |
| `tile_width` / `tile_height` | `uint32` | Kích thước tile (px) | — |
| `orig_width` / `orig_height` | `uint32` | Kích thước ảnh gốc (px) — để clamp toạ độ | `> 0` |
| `image` | `sensor_msgs/Image` | Pixel của tile | encoding **`bgr8`** |

**Bên publish chịu trách nhiệm** đặt `image_id` duy nhất mỗi frame và offset đúng để bbox ánh xạ về ảnh gốc chính xác.

---

## 2. Output topic — `/grass_segments`

- **Type:** `robot_ai_interfaces/msg/GrassSegmentationArray`
- **Publisher:** `yolo_bridge`
- **Subscriber:** downstream consumer
- **Ngữ nghĩa:** **1 message / ảnh gốc**, phát khi gom đủ `num_tiles` tile (hoặc hết `AGG_TIMEOUT`). Bbox/polygon là toạ độ **GLOBAL** theo ảnh gốc, đã clamp `[0..orig_w]×[0..orig_h]`. Ảnh không có vật → `segments` rỗng (vẫn phát).

### `GrassSegmentationArray.msg`
| Field | Type | Ý nghĩa |
|---|---|---|
| `header` | `std_msgs/Header` | `stamp` giữ theo tile nguồn; `frame_id = image_id` |
| `image_id` | `string` | ID ảnh gốc/frame |
| `segments` | `GrassSegment[]` | danh sách segment/detection |

### `GrassSegment.msg`
| Field | Type | Ý nghĩa |
|---|---|---|
| `class_name` | `string` | tên class model trả về, vd `grass` |
| `score` | `float32` | confidence `[0..1]` |
| `bbox` | `robot_ai_interfaces/BBox2D` | bbox GLOBAL dạng center + size (`center_x, center_y, size_x, size_y, theta`) |
| `polygon` | `geometry_msgs/Polygon` | polygon GLOBAL nếu YOLO segmentation model trả mask polygon |

> Hiện ZeroMQ reply vẫn là JSON. Với model detection thường, `polygon=[]`. Với YOLO segmentation model, `polygon` được map từ tile-local sang ảnh gốc.

---

## 3. Internal protocol — ZeroMQ (bridge ⇄ yolo_server)

> Nội bộ pipeline, **không dành cho bên thứ 3**. Ghi lại để bảo trì.

- **Transport:** ZeroMQ **REQ/REP**, `tcp://127.0.0.1:${YOLO_ZMQ_PORT}` (mặc định 5555), lockstep.
- **Request** (bridge→server): raw bytes = **ảnh JPEG** của 1 tile.
- **Reply** (server→bridge): UTF-8 **JSON**, list các object/segment toạ độ **LOCAL** (trong tile):
  ```json
  [{"class_id": 0, "class_name": "grass", "confidence": 0.87, "bbox": [x1, y1, x2, y2], "polygon": [[x, y]]}]
  ```
- `polygon` optional; có khi model segmentation trả mask polygon. Detection-only model trả `polygon: []`.
- **Lỗi:** ảnh hỏng/rỗng → server trả `[]`. Bridge timeout (`RCVTIMEO`) → bỏ tile đó, tái tạo socket, tiếp tục.

---

## 4. Environment variables

| Biến | Service | Mặc định | Ý nghĩa |
|---|---|---|---|
| `YOLO_ZMQ_PORT` | ros2 + yolo | `5555` | Cổng ZMQ (2 bên phải khớp) |
| `YOLO_MODEL` | yolo | `/app/models/yolo26n-seg.pt` | Model weights (đổi sang weights cỏ khi có) |
| `YOLO_TARGET_CLASSES` | yolo | (rỗng) | Lọc class, ngăn cách dấu phẩy (vd `grass`); rỗng = tất cả |
| `SAMPLE_DIR` | ros2 | `/images` | Folder ảnh cho `sample_publisher` (mount từ `shared/images`) |
| `RESULT_SAVE` / `RESULT_FORMAT` / `RESULT_DIR` | ros2 | `1` / `both` / `/output` | `result_writer` ghi đè output mới nhất vào `latest_segments.json` / `latest_annotated.jpg` |
| `ROS_DOMAIN_ID` | ros2 | `0` | ROS2 domain |

**Tham số node `sample_publisher`** (launch): `mode` (`simulate_tiles`|`passthrough`), `cols` (4), `rows` (3), `period_s` (2.0).

---

## 5. Quy ước toạ độ

- **LOCAL:** trong tile, gốc `(0,0)` ở góc trên-trái tile — do `yolo_server` trả.
- **GLOBAL:** trong ảnh gốc — `gx = x_offset + lx`, `gy = y_offset + ly`, clamp `[0..orig]`. Do `yolo_bridge` tính (`geometry.local_to_global`).
- bbox format nội bộ `[x1, y1, x2, y2]`; ra `GrassSegment.bbox` đổi sang center + size.
- polygon format nội bộ `[[x, y], ...]`; ra `GrassSegment.polygon.points[]`.

---

## 6. Versioning contract

- Theo **SemVer** cho contract này (độc lập version code).
- **MAJOR**: đổi/xoá field, đổi type, đổi ngữ nghĩa gom, **xoá topic** → phá tương thích.
- **MINOR**: thêm field optional, thêm topic/env mới (tương thích ngược).
- **PATCH**: làm rõ tài liệu, sửa mặc định không phá vỡ.
- Mỗi thay đổi cập nhật **Contract version** ở đầu file + ghi `CHANGELOG.md`, thông báo bên thứ 3 & downstream.
- **2.0.0:** bỏ topic tương thích `/grass_detections` (`vision_msgs/Detection2DArray`); `/grass_segments` là output DUY NHẤT.
