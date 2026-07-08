# 0003 — Contract tile, toạ độ và aggregate

- **Status:** Accepted
- **Date:** 2026-07-08

## Context
Ảnh gốc 4K được chia thành nhiều tile (mặc định 4×3=12) để detect. Cần: (1) truyền metadata offset của tile qua ROS2; (2) ánh xạ bbox từ tile về ảnh gốc; (3) gom kết quả nhiều tile thành 1 kết quả/ảnh. Tiler thật do bên thứ 3 làm.

## Decision
- **Custom msg `TileImage`** (package `robot_ai_interfaces`) mang `image_id, tile_index, num_tiles, x/y_offset, tile/orig size, image` — chọn typed msg thay vì nhét metadata vào `frame_id` để rõ ràng, có kiểu.
- **`yolo_server` trả bbox LOCAL**; **`yolo_bridge` đổi LOCAL→GLOBAL** (cộng offset, clamp `[0..orig]`) — giữ YOLO không biết layout.
- **Aggregate theo `image_id`** đến khi đủ `num_tiles` hoặc hết timeout; `image_id` phải duy nhất mỗi frame; dedup tile trùng.
- **Output `vision_msgs/Detection2DArray`** (chuẩn ROS2) thay vì String JSON.

## Consequences
- (+) Contract typed, rõ cho bên thứ 3; downstream dùng message chuẩn.
- (+) Logic toạ độ/gom là hàm thuần → test kỹ (boundary/timeout/dedup).
- (−) Cần build package interfaces (rosidl).
- (−) `image_id` duy nhất là trách nhiệm bên publish; nếu lặp lại, aggregator (đúng thiết kế) sẽ bỏ frame sau.
