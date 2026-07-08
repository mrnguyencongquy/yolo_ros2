# yolo_ros2 — Grass detection AI stack

ROS2 Jazzy + YOLO (Ultralytics) tiling detection pipeline. Dev trên PC x86 (CUDA), verify trên Jetson.

## Chạy

```bash
cd robot-ai-stack
cp env.pc.example .env        # PC   (hoặc env.jetson.example trên Jetson)
docker compose up --build
```

Xem `docs/superpowers/specs/` cho thiết kế, `docs/superpowers/test-specs/` cho test spec, `docs/superpowers/plans/` cho kế hoạch triển khai.
