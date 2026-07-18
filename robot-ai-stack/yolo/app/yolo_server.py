import json
import os
import sys


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def _get_port() -> int:
    raw = os.environ.get("YOLO_ZMQ_PORT", "5555")
    try:
        return int(raw)
    except ValueError:
        print(f"[yolo_server] invalid YOLO_ZMQ_PORT: {raw!r}", file=sys.stderr)
        sys.exit(2)


def _model_revision(model_path: str) -> tuple[str, int, int] | None:
    """Return a revision that changes when a model file or active symlink changes."""
    try:
        stat = os.stat(model_path)
    except OSError:
        return None
    return (os.path.realpath(model_path), stat.st_mtime_ns, stat.st_size)


def main() -> None:
    port = _get_port()
    model_path = os.environ.get("YOLO_MODEL", "/models/yolo26n-seg.pt")
    if not os.path.exists(model_path):
        print(f"[yolo_server] model not found: {model_path}", file=sys.stderr)
        sys.exit(3)
    auto_reload = _truthy(os.environ.get("YOLO_MODEL_AUTO_RELOAD", "0"))

    import torch
    import zmq
    from ultralytics import YOLO

    from app.inference import decode_jpeg, run_inference

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[yolo_server] device={device} model={model_path}", flush=True)
    model = YOLO(model_path)
    model_revision = _model_revision(model_path)
    raw_targets = os.environ.get("YOLO_TARGET_CLASSES")
    targets = {t.strip() for t in raw_targets.split(",")} if raw_targets else None

    ctx = zmq.Context()
    sock = ctx.socket(zmq.REP)
    sock.bind(f"tcp://*:{port}")
    print(f"[yolo_server] listening on tcp://*:{port}", flush=True)
    while True:
        data = sock.recv()
        if auto_reload:
            next_revision = _model_revision(model_path)
            if next_revision is None:
                print(f"[yolo_server] model unavailable; keeping current model: {model_path}", file=sys.stderr)
            elif next_revision != model_revision:
                try:
                    candidate = YOLO(model_path)
                except Exception as exc:
                    print(f"[yolo_server] reload failed; keeping current model: {exc}", file=sys.stderr)
                else:
                    model = candidate
                    model_revision = next_revision
                    print(f"[yolo_server] reloaded model={model_path}", flush=True)
        dets = run_inference(model, decode_jpeg(data), targets)
        sock.send_string(json.dumps(dets))


if __name__ == "__main__":
    main()
