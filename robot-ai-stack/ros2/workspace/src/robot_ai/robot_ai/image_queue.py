from collections import deque
from pathlib import Path


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")


class ImageFileQueue:
    """Queues new or updated image files from a directory without reprocessing them."""

    def __init__(self, directory: str):
        self._directory = Path(directory)
        self._processed: dict[str, tuple[int, int]] = {}
        self._queued: dict[str, tuple[int, int]] = {}
        self._pending: deque[tuple[str, tuple[int, int]]] = deque()

    def refresh(self) -> None:
        """Discover supported images that are new or have changed on disk."""
        if not self._directory.is_dir():
            return
        for path in sorted(self._directory.iterdir()):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            revision = (stat.st_mtime_ns, stat.st_size)
            name = path.name
            if self._processed.get(name) == revision or self._queued.get(name) == revision:
                continue
            self._queued[name] = revision
            self._pending.append((name, revision))

    def pop(self) -> tuple[str, tuple[int, int]] | None:
        if not self._pending:
            return None
        name, revision = self._pending.popleft()
        self._queued.pop(name, None)
        return name, revision

    def mark_processed(self, name: str, revision: tuple[int, int]) -> None:
        self._processed[name] = revision
