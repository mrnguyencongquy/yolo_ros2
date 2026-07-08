# Contributing

## Môi trường dev

- Python 3.12, ROS2 Jazzy + `colcon` (cho phần ROS2), Docker + Compose.
- Logic thuần test được **không cần ROS2/Docker** (chỉ cần `numpy opencv-python pyzmq pytest`).

## Chạy test trước khi commit

```bash
# Unit test logic thuần
cd robot-ai-stack/ros2/workspace/src/robot_ai && PYTHONPATH=$PWD python3 -m pytest test/ -v
cd robot-ai-stack/yolo && python3 -m pytest tests/ -v

# Build ROS2 (nếu đụng node/msg)
cd robot-ai-stack/ros2/workspace && colcon build && source install/setup.bash

# E2E (nếu đụng pipeline/Docker)
cd robot-ai-stack && cp env.pc.example .env && docker compose up --build
```

Mọi thay đổi **logic thuần** phải kèm/chỉnh test tương ứng (xem `docs/superpowers/test-specs/` để biết ca cần phủ).

## Quy ước commit — Conventional Commits

`type(scope): mô tả` — `type` ∈ `feat, fix, docs, test, chore, refactor`. Ví dụ:
```
feat(robot_ai): add overlap NMS across tiles
fix(yolo): handle empty model dir
docs(interfaces): bump contract to 1.2.0
```

## Nhánh & PR

- Tạo nhánh từ `main`: `feat/<tên>` hoặc `fix/<tên>`.
- 1 PR = 1 mục tiêu; mô tả + cách test.
- CI (`.github/workflows/ci.yml`) phải xanh trước khi merge.

## Cập nhật tài liệu (bắt buộc khi liên quan)

- Đổi **contract** (msg/topic/ZMQ/env) → cập nhật `docs/interfaces.md` + **bump Contract version** + ghi `CHANGELOG.md` + báo bên thứ 3/downstream.
- Đổi kiến trúc → cập nhật `docs/ARCHITECTURE.md`.
- Quyết định kiến trúc mới → thêm ADR (`docs/adr/`), không sửa ADR cũ.

## Versioning

- Code + contract theo **SemVer**. Release: bump `version` trong `package.xml`, cập nhật `CHANGELOG.md`, tag `vX.Y.Z`.
