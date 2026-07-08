# Workflow / Input Output Metadata

Tài liệu này mô tả luồng dữ liệu hiện tại của stack ROS2 + YOLO: dữ liệu đi vào từ đâu, metadata dùng để làm gì, output ra topic nào, và từng thành phần xử lý gì.

## 1. Hai Chế Độ Vận Hành

### Dev / test mode hiện tại

Trong môi trường dev, chưa có tiler bên thứ 3. Node `sample_publisher` đứng thay tiler thật:

```text
shared/images/*.jpg
  -> sample_publisher
  -> tự chia ảnh thành tile 4x3
  -> publish robot_ai_interfaces/TileImage lên /image_tiles
  -> yolo_bridge
  -> yolo_server
  -> /grass_detections
```

`sample_publisher` chỉ dùng để verify pipeline trước khi tích hợp tiler thật. Nó không phải thành phần production bắt buộc.

### Production mode dự kiến

Trong production, bên thứ 3 chịu trách nhiệm chia ảnh 4K thành tile và publish thẳng vào ROS2:

```text
bên thứ 3 / tiler thật
  -> 4K image -> 12 tile + metadata
  -> publish TileImage lên /image_tiles
  -> yolo_bridge
  -> yolo_server
  -> /grass_detections
```

Khi có tiler thật, không cần chạy `sample_publisher`; chỉ cần `yolo_bridge` subscribe `/image_tiles`.

## 2. Input Chính: `/image_tiles`

Topic:

```text
/image_tiles
```

Type:

```text
robot_ai_interfaces/msg/TileImage
```

Publisher:

- Dev: `sample_publisher`
- Production: tiler bên thứ 3

Subscriber:

- `yolo_bridge`

Mỗi message là một tile của một ảnh gốc. Nếu một ảnh gốc chia thành 12 tile thì sẽ có 12 message `TileImage` có cùng `image_id`.

## 3. Metadata Trong `TileImage`

`TileImage` gồm dữ liệu pixel của tile và metadata để bridge map kết quả YOLO về ảnh gốc.

```text
std_msgs/Header header
string image_id
uint16 tile_index
uint16 tile_row
uint16 tile_col
uint16 num_tiles
uint32 x_offset
uint32 y_offset
uint32 tile_width
uint32 tile_height
uint32 orig_width
uint32 orig_height
sensor_msgs/Image image
```

### Ý Nghĩa Từng Field

| Field | Vai trò |
|---|---|
| `header` | Timestamp và frame nguồn. Output detection copy lại header để downstream trace frame. |
| `image_id` | ID ảnh gốc. Đây là khóa để gom các tile cùng một ảnh. Phải duy nhất cho mỗi frame. |
| `tile_index` | Số thứ tự tile trong ảnh gốc, ví dụ `0..11`. Dùng để dedup và biết tile nào đã nhận. |
| `tile_row` | Hàng của tile trong grid, ví dụ `0..2` nếu chia 3 hàng. Chủ yếu để debug/trace. |
| `tile_col` | Cột của tile trong grid, ví dụ `0..3` nếu chia 4 cột. Chủ yếu để debug/trace. |
| `num_tiles` | Tổng số tile của ảnh gốc. Bridge dùng để biết khi nào gom đủ và publish output. |
| `x_offset` | Tọa độ X góc trái trên của tile trong ảnh gốc. Dùng để đổi bbox local thành global. |
| `y_offset` | Tọa độ Y góc trái trên của tile trong ảnh gốc. Dùng để đổi bbox local thành global. |
| `tile_width` | Chiều rộng tile, đơn vị pixel. |
| `tile_height` | Chiều cao tile, đơn vị pixel. |
| `orig_width` | Chiều rộng ảnh gốc. Dùng để clamp bbox không vượt biên. |
| `orig_height` | Chiều cao ảnh gốc. Dùng để clamp bbox không vượt biên. |
| `image` | Pixel của tile, hiện dùng encoding `bgr8`. |

## 4. Ví Dụ Chia Ảnh 4K Thành 12 Tile

Ảnh gốc:

```text
orig_width  = 3840
orig_height = 2160
cols = 4
rows = 3
num_tiles = 12
```

Kích thước tile chuẩn:

```text
tile_width  = 960
tile_height = 720
```

Một vài tile mẫu:

| tile_index | row | col | x_offset | y_offset | tile_width | tile_height |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 | 960 | 720 |
| 1 | 0 | 1 | 960 | 0 | 960 | 720 |
| 2 | 0 | 2 | 1920 | 0 | 960 | 720 |
| 3 | 0 | 3 | 2880 | 0 | 960 | 720 |
| 4 | 1 | 0 | 0 | 720 | 960 | 720 |
| 8 | 2 | 0 | 0 | 1440 | 960 | 720 |
| 11 | 2 | 3 | 2880 | 1440 | 960 | 720 |

Nếu kích thước ảnh không chia hết cho grid, cột/hàng cuối giữ phần dư để phủ hết ảnh, không bỏ pixel.

## 5. Vì Sao Cần `x_offset` Và `y_offset`

YOLO chỉ nhìn thấy từng tile, nên bbox YOLO trả về là tọa độ local trong tile.

Ví dụ tile có:

```text
x_offset = 960
y_offset = 720
```

YOLO trả bbox local:

```text
[x1, y1, x2, y2] = [10, 20, 50, 60]
```

Bridge đổi sang tọa độ global trên ảnh gốc:

```text
global_x1 = 960 + 10 = 970
global_y1 = 720 + 20 = 740
global_x2 = 960 + 50 = 1010
global_y2 = 720 + 60 = 780
```

Kết quả:

```text
[970, 740, 1010, 780]
```

Downstream chỉ cần dùng tọa độ ảnh gốc; không cần biết detection đến từ tile nào.

## 6. `yolo_bridge` Xử Lý Gì

`yolo_bridge` là node ROS2 nằm giữa ROS topic và YOLO server.

Với mỗi `TileImage` nhận từ `/image_tiles`, nó làm:

1. Convert `sensor_msgs/Image` thành OpenCV image bằng `cv_bridge`.
2. Encode tile thành JPEG bytes bằng `cv2.imencode(".jpg", frame)`.
3. Gửi JPEG bytes qua ZeroMQ REQ tới `yolo_server`.
4. Nhận JSON detection từ `yolo_server`.
5. Parse JSON thành list detection.
6. Đổi bbox local trong tile thành bbox global trên ảnh gốc bằng `x_offset`, `y_offset`, `orig_width`, `orig_height`.
7. Gửi detection global vào aggregator theo `image_id`.
8. Khi đủ `num_tiles` hoặc timeout, publish `Detection2DArray` lên `/grass_detections`.

## 7. YOLO Server Xử Lý Gì

`yolo_server` không biết ROS2 và không biết metadata tile.

Nó chỉ làm:

```text
JPEG bytes
  -> decode thành OpenCV image
  -> chạy YOLO model trên tile
  -> trả JSON detections local
```

Reply JSON có dạng:

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

`bbox` trong JSON là tọa độ local trong tile. `yolo_server` không cộng offset.

## 8. Output Chính: `/grass_detections`

Topic:

```text
/grass_detections
```

Type:

```text
vision_msgs/msg/Detection2DArray
```

Publisher:

- `yolo_bridge`

Subscriber:

- Hiện repo chưa có downstream node riêng.
- Có thể dùng `ros2 topic echo /grass_detections` để subscribe và print.
- Production downstream có thể là module điều hướng, module vẽ bbox, logger, hoặc controller robot.

Một ảnh gốc sẽ tạo một message `/grass_detections` khi:

- đã nhận đủ `num_tiles`, hoặc
- hết timeout gom tile.

Nếu ảnh không có object, vẫn có thể publish message với `detections=[]`.

## 9. Format Detection Output

Mỗi detection trong `Detection2DArray.detections` có dạng chính:

```text
header.frame_id
results[0].hypothesis.class_id
results[0].hypothesis.score
bbox.center.position.x
bbox.center.position.y
bbox.size_x
bbox.size_y
```

Ví dụ:

```yaml
header:
  frame_id: 4k_2.jpg#53
results:
- hypothesis:
    class_id: handbag
    score: 0.2627880871295929
bbox:
  center:
    position:
      x: 3409.312713623047
      y: 1467.566463470459
    theta: 0.0
  size_x: 41.82025146484375
  size_y: 55.13292694091797
```

Ý nghĩa:

- `frame_id`: ảnh gốc/frame sinh ra detection.
- `class_id`: tên class YOLO detect được.
- `score`: confidence.
- `center.x`, `center.y`: tâm bbox trên ảnh gốc, đơn vị pixel.
- `size_x`, `size_y`: kích thước bbox trên ảnh gốc, đơn vị pixel.

Đổi từ center/size sang góc trái trên và góc phải dưới:

```text
x1 = center_x - size_x / 2
y1 = center_y - size_y / 2
x2 = center_x + size_x / 2
y2 = center_y + size_y / 2
```

## 10. Cách Kiểm Tra Bằng CLI

Vào container ROS2:

```bash
docker exec -it ros2_node bash
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash
```

Xem topic:

```bash
ros2 topic list
ros2 topic info /image_tiles -v
ros2 topic info /grass_detections -v
```

Xem input tile:

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

Xem log:

```bash
docker logs -f ros2_node
docker logs -f yolo_detector
```

## 11. Trách Nhiệm Tích Hợp Của Bên Thứ 3

Bên thứ 3 không cần biết YOLO hoặc `/grass_detections`. Bên thứ 3 chỉ cần publish đúng contract `/image_tiles`.

Bắt buộc đúng:

- `image_id` duy nhất cho mỗi ảnh gốc/frame.
- Các tile cùng ảnh gốc dùng cùng `image_id`.
- `tile_index` duy nhất trong cùng `image_id`.
- `num_tiles` đúng tổng số tile.
- `x_offset`, `y_offset` đúng vị trí tile trong ảnh gốc.
- `orig_width`, `orig_height` đúng kích thước ảnh gốc.
- `image` là pixel tile đúng encoding.

Nếu metadata sai, YOLO vẫn có thể detect được object trong tile, nhưng bbox global trên ảnh gốc sẽ sai.
