import zmq


class ZmqReqClient:
    """REQ client: timeout → trả None và tái tạo socket (REQ sau timeout phải recreate)."""

    def __init__(self, endpoint: str, timeout_ms: int = 2000):
        self._endpoint = endpoint
        self._timeout = timeout_ms
        self._ctx = zmq.Context.instance()
        self._sock = None
        self._connect()

    def _connect(self) -> None:
        if self._sock is not None:
            self._sock.close(0)
        self._sock = self._ctx.socket(zmq.REQ)
        self._sock.setsockopt(zmq.RCVTIMEO, self._timeout)
        self._sock.setsockopt(zmq.LINGER, 0)
        self._sock.connect(self._endpoint)

    def request(self, data: bytes):
        """Gửi + chờ reply. None nếu timeout (đã tái tạo socket)."""
        try:
            self._sock.send(data)
            return self._sock.recv()
        except zmq.Again:
            self._connect()
            return None
