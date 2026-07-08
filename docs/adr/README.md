# Architecture Decision Records (ADR)

Mỗi file ghi lại **một quyết định kiến trúc**: bối cảnh, quyết định, hệ quả. ADR là **bất biến** — không sửa quyết định cũ; nếu đổi ý thì tạo ADR mới và đánh dấu ADR cũ là `Superseded by 000X`.

Format: [Michael Nygard](https://github.com/joelparkerhenderson/architecture-decision-record). Đặt tên `000N-tieu-de-ngan.md`.

| # | Quyết định | Trạng thái |
|---|---|---|
| [0001](0001-decouple-yolo-from-ros2-via-zeromq.md) | Tách YOLO khỏi ROS2 qua ZeroMQ | Accepted |
| [0002](0002-platform-split-via-compose-override.md) | Tách nền tảng PC/Jetson bằng Compose override | Accepted |
| [0003](0003-tile-coordinate-contract.md) | Contract tile + toạ độ + aggregate | Accepted |
| [0004](0004-pc-base-image-pytorch-cuda.md) | Base image PC = pytorch/pytorch CUDA | Accepted |
