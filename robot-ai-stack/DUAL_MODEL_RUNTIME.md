# Dual-model runtime

The dual-model stack runs the two configured model files independently on one GPU. Both receive the same `/image_tiles` messages, but publish separate `DetectedInstanceArray` topics:

| Model configuration | ZMQ port | Output topic | JSON directory |
| --- | --- | --- | --- |
| `YOLO_BASE_MODEL` (default: `yolo11n.pt`) | `5555` | `/models/<filename>/detected_instances` | `/output/<filename>` |
| `YOLO_TRAINED_MODEL` (default: `yolo26n-seg.pt`) | `5556` | `/models/<filename>/detected_instances` | `/output/<filename>` |

## Runtime folders

Model and input folders are mounted at runtime. Adding data or replacing a model does not require an image build.

Each writer derives both its output topic and JSON directory from the configured model filename, without the `.pt` extension. Characters that are invalid in ROS 2 topic names (anything other than alphanumerics and `_`, including `-` and `.`) are replaced with `_`. For example, `/models/yolo26n-seg-v4.pt` publishes to `/models/yolo26n_seg_v4/detected_instances` and writes to `/output/yolo26n_seg_v4/latest_detected_instances.json`. The two output directories prevent the two models from overwriting each other's latest JSON.

```text
models/
  yolo11n.pt
  yolo26n-seg.pt
shared/images/
  frame-0001.jpg
shared/output/
```

Use an atomic rename when a producer writes an image or model: write `file.part`, then rename it to `.jpg` or `.pt`. Do not overwrite a model file while it is being loaded.

## Stop the single-model stack first

All services use `network_mode: host`, so a `yolo_detector` container left running from the single-model stack keeps port `5555` bound. `yolo_base` then crash-loops (`Address already in use`) and the base bridge silently receives results from the old container's model. The dual-model overlay only hides the `yolo` service from `up`; it does not stop an already-running container:

```bash
docker rm -f yolo_detector 2>/dev/null || true
```

## Start on a PC with NVIDIA GPU

```bash
export COMPOSE_FILE=docker-compose.yml:docker-compose.pc.yml:docker-compose.dual-model.yml:docker-compose.dual-model.pc.yml
docker compose up --build -d
```

## Start on Jetson

```bash
export COMPOSE_FILE=docker-compose.yml:docker-compose.jetson.yml:docker-compose.dual-model.yml:docker-compose.dual-model.jetson.yml
docker compose up --build -d
```

Set `SAMPLE_WATCH_NEW_FILES=true` to process each new or updated image from the mounted `IMAGE_DIR` once. This is intended for development/file-drop ingestion. A production camera or partner node should publish `TileImage` directly to `/image_tiles`.

## Changing a model

The safe default is to restart only the affected model after placing a new version in `MODEL_DIR`:

```bash
docker compose restart yolo_trained
```

Set `YOLO_MODEL_AUTO_RELOAD=1` to reload an updated model file before the next inference request. The server keeps the old model if loading fails. Reloading temporarily holds old and new weights in GPU memory, so keep it disabled on memory-constrained Jetson devices unless it has been benchmarked.
