from dataclasses import dataclass


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float


def normalize_bbox(b: BBox) -> BBox:
    """Đảm bảo x1<=x2, y1<=y2 (bbox có thể bị đảo từ model)."""
    return BBox(min(b.x1, b.x2), min(b.y1, b.y2), max(b.x1, b.x2), max(b.y1, b.y2))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(v, hi))


def local_to_global(b: BBox, x_offset: int, y_offset: int, orig_w: int, orig_h: int) -> BBox:
    """Dời bbox toạ độ tile → toạ độ ảnh gốc, clamp về [0..orig]."""
    b = normalize_bbox(b)
    return BBox(
        _clamp(b.x1 + x_offset, 0, orig_w),
        _clamp(b.y1 + y_offset, 0, orig_h),
        _clamp(b.x2 + x_offset, 0, orig_w),
        _clamp(b.y2 + y_offset, 0, orig_h),
    )


def point_local_to_global(x: float, y: float, x_offset: int, y_offset: int, orig_w: int, orig_h: int) -> tuple[float, float]:
    """Dời 1 điểm tile-local → ảnh gốc, clamp về [0..orig]."""
    return (
        _clamp(float(x) + x_offset, 0, orig_w),
        _clamp(float(y) + y_offset, 0, orig_h),
    )
