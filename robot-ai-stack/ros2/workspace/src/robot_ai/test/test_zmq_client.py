import os
import threading
from pathlib import Path

import pytest
import zmq

from robot_ai.zmq_client import ZmqReqClient


def test_timeout_returns_none_and_recovers():
    # Không có server → recv timeout → None; sau đó server lên → request OK.
    sock_path = Path(f"/tmp/zmq-client-test-{os.getpid()}.sock")
    sock_path.unlink(missing_ok=True)
    endpoint = f"ipc://{sock_path}"
    client = ZmqReqClient(endpoint, timeout_ms=150)
    assert client.request(b"x") is None        # TC-39 timeout -> None (socket recreated)

    ctx = zmq.Context.instance()
    rep = ctx.socket(zmq.REP)
    try:
        rep.bind(endpoint)
    except zmq.ZMQError as exc:
        rep.close(0)
        client._sock.close(0)
        sock_path.unlink(missing_ok=True)
        pytest.skip(f"ZMQ IPC bind unavailable in this environment: {exc}")

    def echo():
        rep.recv()
        rep.send(b"pong")

    t = threading.Thread(target=echo, daemon=True)
    t.start()

    assert client.request(b"ping") == b"pong"   # TC-37 recovers after prior timeout
    t.join(timeout=2)
    client._sock.close(0)
    rep.close(0)
    sock_path.unlink(missing_ok=True)
