import numpy as np

from robot_ai.tiling import compute_tiles, split_image


def test_4x3_exact():                          # TC-17
    tiles = compute_tiles(3840, 2160, 4, 3)
    assert len(tiles) == 12
    assert (tiles[0].x_offset, tiles[0].y_offset) == (0, 0)
    assert (tiles[0].width, tiles[0].height) == (960, 720)
    assert (tiles[-1].x_offset, tiles[-1].y_offset) == (2880, 1440)


def test_remainder_in_last():                  # TC-18
    tiles = compute_tiles(3841, 2161, 4, 3)
    assert tiles[-1].width == 3841 - 2880       # 961
    assert tiles[-1].height == 2161 - 1440      # 721
    row0 = [t for t in tiles if t.row == 0]
    assert sum(t.width for t in row0) == 3841


def test_split_image_shapes_and_deterministic():  # TC-51
    img = np.zeros((2160, 3840, 3), dtype=np.uint8)
    a = split_image(img, 4, 3)
    b = split_image(img, 4, 3)
    assert len(a) == 12
    spec, tile = a[0]
    assert tile.shape == (720, 960, 3)
    assert [s.__dict__ for s, _ in a] == [s.__dict__ for s, _ in b]
