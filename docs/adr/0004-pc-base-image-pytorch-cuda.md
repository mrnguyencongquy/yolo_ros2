# 0004 — Base image PC = pytorch/pytorch CUDA

- **Status:** Accepted
- **Date:** 2026-07-08

## Context
Bản PC (x86, RTX 3060) cần base image có PyTorch + CUDA để chạy YOLO trên GPU. Cân nhắc: `pytorch/pytorch:*-cuda12-cudnn9-runtime` (+ pip ultralytics) vs `ultralytics/ultralytics` (batteries-included: ultralytics + onnx/tensorrt sẵn).

## Decision
Dùng **`pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime` + pip `ultralytics`**. Lý do: khớp cấu trúc Dockerfile của Jetson (dustynv/pytorch cũng là pytorch base + pip ultralytics) → dễ đối chiếu 2 nền tảng; image nhẹ hơn. Định dạng model không bị giới hạn bởi base (ultralytics tự chọn backend theo đuôi file); cần ONNX chỉ thêm `onnxruntime-gpu`.

## Consequences
- (+) Cấu trúc 2 Dockerfile song song, dễ bảo trì.
- (+) Tự kiểm soát dependency; image nhỏ hơn ultralytics/ultralytics.
- (−) Muốn export ONNX/TensorRT phải cài thêm gói.
- (−) Tag base phải pin và kiểm khi nâng CUDA/driver.
