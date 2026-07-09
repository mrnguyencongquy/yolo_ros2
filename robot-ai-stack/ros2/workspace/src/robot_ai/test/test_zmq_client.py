import socket
import threading

import pytest
import zmq

from robot_ai.zmq_client import ZmqReqClient


def _free_port() -> int:
    """Lấy 1 TCP port trống trên loopback (tránh hardcode -> hết flaky)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_timeout_returns_none_and_recovers():
    # Dùng TCP loopback cho khớp transport production (yolo_bridge/yolo_server).
    endpoint = f"tcp://127.0.0.1:{_free_port()}"
    client = ZmqReqClient(endpoint, timeout_ms=200)
    assert client.request(b"x") is None        # TC-39 timeout -> None (socket recreated)

    ctx = zmq.Context.instance()
    rep = ctx.socket(zmq.REP)
    rep.setsockopt(zmq.LINGER, 0)
    try:
        rep.bind(endpoint)
    except zmq.ZMQError as exc:
        rep.close(0)
        client._sock.close(0)
        pytest.skip(f"ZMQ TCP bind unavailable in this environment: {exc}")

    def echo():
        rep.recv()
        rep.send(b"pong")

    t = threading.Thread(target=echo, daemon=True)
    t.start()

    assert client.request(b"ping") == b"pong"   # TC-37 recovers after prior timeout
    t.join(timeout=2)
    client._sock.close(0)
    rep.close(0)
