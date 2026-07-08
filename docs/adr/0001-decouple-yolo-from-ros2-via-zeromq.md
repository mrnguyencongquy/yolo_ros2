# 0001 — Tách YOLO khỏi ROS2 qua ZeroMQ

- **Status:** Accepted
- **Date:** 2026-07-08

## Context
Code ban đầu (`detector.py`) import `rclpy`/`cv_bridge` nhưng base image YOLO (`dustynv/pytorch`) không cài ROS2 → crash. Muốn đổi model YOLOv5/v8/v11/26 tự do, tránh xung đột `cv_bridge`, và giữ YOLO không lệ thuộc ROS2. Cân nhắc: (A) cài ROS2 vào container YOLO; (B) IPC ZeroMQ; (C) IPC Zenoh.

## Decision
Dùng **ZeroMQ REQ/REP** làm IPC giữa `yolo_bridge` (ROS2) và `yolo_server` (thuần Python). YOLO chỉ nhận JPEG → trả bbox LOCAL (JSON). Chọn ZeroMQ thay Zenoh vì bài toán là request/response 1-máy, ZeroMQ nhẹ và đơn giản hơn; Zenoh phù hợp hơn nếu sau này cần runtime xuyên mạng PC↔Jetson.

## Consequences
- (+) YOLO container không cần ROS2; đổi model dễ; không xung đột cv_bridge.
- (+) Logic ROS2 (toạ độ, gom) nằm ở bridge — YOLO "ngu", dễ test/thay.
- (−) REQ/REP lockstep giới hạn throughput ở tốc độ inference (chấp nhận cho MVP).
- (−) Thêm 1 chặng serialize (JPEG) — chi phí nhỏ ở localhost/host-network.
