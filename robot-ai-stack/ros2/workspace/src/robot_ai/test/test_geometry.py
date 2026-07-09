from robot_ai.geometry import BBox, normalize_bbox, local_to_global, point_local_to_global


def test_happy_shift():                       # TC-56
    g = local_to_global(BBox(10, 20, 50, 60), 960, 720, 3840, 2160)
    assert (g.x1, g.y1, g.x2, g.y2) == (970, 740, 1010, 780)


def test_inverted_bbox_normalized():          # TC-01
    assert normalize_bbox(BBox(50, 60, 10, 20)) == BBox(10, 20, 50, 60)


def test_negative_clamped_to_zero():          # TC-02
    g = local_to_global(BBox(-5, -5, 10, 10), 0, 0, 3840, 2160)
    assert (g.x1, g.y1) == (0, 0)


def test_edge_equals_orig_no_extra_clamp():   # TC-10
    g = local_to_global(BBox(0, 0, 960, 720), 2880, 1440, 3840, 2160)
    assert (g.x2, g.y2) == (3840, 2160)


def test_just_outside_clamped():              # TC-11
    g = local_to_global(BBox(0, 0, 961, 0), 2880, 0, 3840, 2160)
    assert g.x2 == 3840


def test_far_corner_tile():                   # TC-12
    g = local_to_global(BBox(959, 719, 960, 720), 2880, 1440, 3840, 2160)
    assert (g.x2, g.y2) == (3840, 2160)


def test_pure_idempotent():                   # TC-38
    args = (BBox(1, 2, 3, 4), 10, 20, 100, 100)
    assert local_to_global(*args) == local_to_global(*args)


def test_point_local_to_global():
    assert point_local_to_global(10, 20, 960, 720, 3840, 2160) == (970.0, 740.0)
    assert point_local_to_global(10, 20, 3835, 2155, 3840, 2160) == (3840, 2160)
