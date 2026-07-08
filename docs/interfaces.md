# Interfaces / Integration Contract — yolo_ros2

> Hợp đồng tích hợp giữa các bên. **Bên thứ 3** (tiler) publish vào `/image_tiles`; **downstream** consume `/grass_detections`. Thay đổi contract phải bump version (mục cuối) và ghi `CHANGELOG`.

**Contract version:** `1.0.0`

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

## 2. Output topic — `/grass_detections`

- **Type:** `vision_msgs/msg/Detection2DArray`
- **Publisher:** `yolo_bridge`
- **Subscriber:** downstream (điều hướng/xử lý)
- **Ngữ nghĩa:** **1 message / ảnh gốc**, phát khi gom đủ `num_tiles` tile (hoặc hết `AGG_TIMEOUT`). Toạ độ **GLOBAL** (theo ảnh gốc), đã clamp `[0..orig_w]×[0..orig_h]`. Ảnh không có vật → `detections` rỗng (vẫn phát).

### Ánh xạ trường
| Detection2DArray | Nguồn |
|---|---|
| `header.stamp` / `header.frame_id` | copy từ `TileImage.header` của tile cuối gom được |
| `detections[i].bbox.center.position.x/y` | tâm bbox GLOBAL (px) |
| `detections[i].bbox.size_x/size_y` | rộng/cao bbox GLOBAL (px) |
| `detections[i].results[0].hypothesis.class_id` | tên class (string, vd `person`, sau này `grass`) |
| `detections[i].results[0].hypothesis.score` | confidence `[0..1]` |

> **Known limitation:** `image_id` **hiện chưa** được đưa vào output (chỉ dùng nội bộ để gom); `header.frame_id` mang frame_id nguồn (vd `sample`). Nếu downstream cần truy vết về đúng ảnh gốc → khuyến nghị map `header.frame_id = image_id` (roadmap).

---

## 3. Internal protocol — ZeroMQ (bridge ⇄ yolo_server)

> Nội bộ pipeline, **không dành cho bên thứ 3**. Ghi lại để bảo trì.

- **Transport:** ZeroMQ **REQ/REP**, `tcp://127.0.0.1:${YOLO_ZMQ_PORT}` (mặc định 5555), lockstep.
- **Request** (bridge→server): raw bytes = **ảnh JPEG** của 1 tile.
- **Reply** (server→bridge): UTF-8 **JSON**, list các object toạ độ **LOCAL** (trong tile):
  ```json
  [{"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [x1, y1, x2, y2]}]
  ```
- **Lỗi:** ảnh hỏng/rỗng → server trả `[]`. Bridge timeout (`RCVTIMEO`) → bỏ tile đó, tái tạo socket, tiếp tục.

---

## 4. Environment variables

| Biến | Service | Mặc định | Ý nghĩa |
|---|---|---|---|
| `YOLO_ZMQ_PORT` | ros2 + yolo | `5555` | Cổng ZMQ (2 bên phải khớp) |
| `YOLO_MODEL` | yolo | `/app/models/yolo26n.pt` | Model weights (đổi sang weights cỏ khi có) |
| `YOLO_TARGET_CLASSES` | yolo | (rỗng) | Lọc class, ngăn cách dấu phẩy (vd `grass`); rỗng = tất cả |
| `SAMPLE_DIR` | ros2 | `/images` | Folder ảnh cho `sample_publisher` (mount từ `shared/images`) |
| `ROS_DOMAIN_ID` | ros2 | `0` | ROS2 domain |

**Tham số node `sample_publisher`** (launch): `mode` (`simulate_tiles`|`passthrough`), `cols` (4), `rows` (3), `period_s` (2.0).

---

## 5. Quy ước toạ độ

- **LOCAL:** trong tile, gốc `(0,0)` ở góc trên-trái tile — do `yolo_server` trả.
- **GLOBAL:** trong ảnh gốc — `gx = x_offset + lx`, `gy = y_offset + ly`, clamp `[0..orig]`. Do `yolo_bridge` tính (`geometry.local_to_global`).
- bbox format nội bộ `[x1, y1, x2, y2]`; ra `Detection2DArray` đổi sang center + size.

---

## 6. Versioning contract

- Theo **SemVer** cho contract này (độc lập version code).
- **MAJOR**: đổi/xoá field, đổi type, đổi ngữ nghĩa gom → phá tương thích.
- **MINOR**: thêm field optional, thêm topic/env mới (tương thích ngược).
- **PATCH**: làm rõ tài liệu, sửa mặc định không phá vỡ.
- Mỗi thay đổi cập nhật **Contract version** ở đầu file + ghi `CHANGELOG.md`, thông báo bên thứ 3 & downstream.
