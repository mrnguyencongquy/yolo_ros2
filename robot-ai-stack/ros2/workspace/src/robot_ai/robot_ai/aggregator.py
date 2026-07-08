import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class _Buffer:
    num_tiles: int
    created: float
    seen: set = field(default_factory=set)
    detections: list = field(default_factory=list)


class DetectionAggregator:
    """Gom detections của các tile cùng image_id đến khi đủ num_tiles hoặc timeout."""

    def __init__(self, timeout_s: float = 2.0, clock: Optional[Callable[[], float]] = None, done_cap: int = 1024):
        self._timeout = timeout_s
        self._clock = clock or time.monotonic
        self._buffers: dict[str, _Buffer] = {}
        self._done: set = set()
        self._done_order: deque = deque(maxlen=done_cap)

    def _mark_done(self, image_id: str) -> None:
        if len(self._done_order) == self._done_order.maxlen:
            self._done.discard(self._done_order[0])
        self._done_order.append(image_id)
        self._done.add(image_id)

    def add(self, image_id: str, tile_index: int, num_tiles: int, dets: list) -> Optional[list]:
        """Thêm 1 tile. Trả list gộp khi đủ tile, ngược lại None."""
        if num_tiles <= 0 or image_id in self._done:
            return None
        buf = self._buffers.get(image_id)
        if buf is None:
            buf = _Buffer(num_tiles=num_tiles, created=self._clock())
            self._buffers[image_id] = buf
        if tile_index in buf.seen:
            return None
        buf.seen.add(tile_index)
        buf.detections.extend(dets)
        if len(buf.seen) >= buf.num_tiles:
            self._mark_done(image_id)
            return self._buffers.pop(image_id).detections
        return None

    def flush_expired(self) -> list:
        """Trả [(image_id, detections)] cho buffer quá timeout; dọn buffer."""
        now = self._clock()
        out = []
        for image_id in list(self._buffers):
            if now - self._buffers[image_id].created >= self._timeout:
                self._mark_done(image_id)
                out.append((image_id, self._buffers.pop(image_id).detections))
        return out
