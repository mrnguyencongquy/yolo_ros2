import json
import os
import sys


def _get_port() -> int:
    raw = os.environ.get("YOLO_ZMQ_PORT", "5555")
    try:
        return int(raw)
    except ValueError:
        print(f"[yolo_server] invalid YOLO_ZMQ_PORT: {raw!r}", file=sys.stderr)
        sys.exit(2)


def main() -> None:
    port = _get_port()
    model_path = os.environ.get("YOLO_MODEL", "/app/models/yolo26n.pt")
    if not os.path.exists(model_path):
        print(f"[yolo_server] model not found: {model_path}", file=sys.stderr)
        sys.exit(3)

    import torch
    import zmq
    from ultralytics import YOLO

    from app.inference import decode_jpeg, run_inference

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[yolo_server] device={device} model={model_path}", flush=True)
    model = YOLO(model_path)
    raw_targets = os.environ.get("YOLO_TARGET_CLASSES")
    targets = {t.strip() for t in raw_targets.split(",")} if raw_targets else None

    ctx = zmq.Context()
    sock = ctx.socket(zmq.REP)
    sock.bind(f"tcp://*:{port}")
    print(f"[yolo_server] listening on tcp://*:{port}", flush=True)
    while True:
        data = sock.recv()
        dets = run_inference(model, decode_jpeg(data), targets)
        sock.send_string(json.dumps(dets))


if __name__ == "__main__":
    main()
