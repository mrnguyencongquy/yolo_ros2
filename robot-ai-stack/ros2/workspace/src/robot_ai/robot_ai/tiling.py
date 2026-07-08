from dataclasses import dataclass


@dataclass(frozen=True)
class TileSpec:
    index: int
    row: int
    col: int
    x_offset: int
    y_offset: int
    width: int
    height: int


def compute_tiles(orig_w: int, orig_h: int, cols: int, rows: int) -> list[TileSpec]:
    """Chia lưới; cột/hàng cuối gánh phần dư → phủ hết, không overlap."""
    base_w, base_h = orig_w // cols, orig_h // rows
    tiles, idx = [], 0
    for r in range(rows):
        for c in range(cols):
            x, y = c * base_w, r * base_h
            w = base_w if c < cols - 1 else orig_w - x
            h = base_h if r < rows - 1 else orig_h - y
            tiles.append(TileSpec(idx, r, c, x, y, w, h))
            idx += 1
    return tiles


def split_image(img, cols: int, rows: int):
    """Trả list (TileSpec, ndarray tile)."""
    h, w = img.shape[:2]
    return [
        (s, img[s.y_offset:s.y_offset + s.height, s.x_offset:s.x_offset + s.width])
        for s in compute_tiles(w, h, cols, rows)
    ]
