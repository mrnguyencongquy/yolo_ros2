# 0002 — Tách nền tảng PC/Jetson bằng Docker Compose override

- **Status:** Accepted
- **Date:** 2026-07-08

## Context
Service `yolo` cần base image khác nhau theo kiến trúc: PC x86 dùng `pytorch/pytorch` CUDA, Jetson dùng `dustynv/pytorch` L4T (ARM64) với `LD_LIBRARY_PATH` và khai báo GPU riêng. Cần một codebase build được cả hai. Cân nhắc: (A) compose override; (B) 1 compose + build ARG/`.env`; (C) 1 Dockerfile theo `TARGETARCH`.

## Decision
Dùng **Compose override**: `docker-compose.yml` (chung) + `docker-compose.pc.yml` / `docker-compose.jetson.yml` (khác biệt base image + GPU). Mỗi máy đặt `COMPOSE_FILE` trong `.env`. Chọn A vì tách bạch rõ, cô lập gọn phần GPU khó tham số hoá, khớp workflow "PC trước, Jetson verify sau".

## Consequences
- (+) `docker compose up` giống nhau ở 2 máy sau khi set `.env`.
- (+) Không đụng code khi đổi nền tảng.
- (−) Có 2 mảnh compose phải giữ đồng bộ.
- (−) File compose base không chạy một mình (thiếu `dockerfile`) — luôn cần override.
