import threading

import zmq

from robot_ai.zmq_client import ZmqReqClient


def test_timeout_returns_none_and_recovers():
    # Không có server → recv timeout → None; sau đó server lên → request OK.
    client = ZmqReqClient("tcp://127.0.0.1:5599", timeout_ms=150)
    assert client.request(b"x") is None        # TC-39 timeout -> None (socket recreated)

    ctx = zmq.Context.instance()
    rep = ctx.socket(zmq.REP)
    rep.bind("tcp://127.0.0.1:5599")

    def echo():
        rep.recv()
        rep.send(b"pong")

    t = threading.Thread(target=echo, daemon=True)
    t.start()

    assert client.request(b"ping") == b"pong"   # TC-37 recovers after prior timeout
    t.join(timeout=2)
    rep.close(0)
