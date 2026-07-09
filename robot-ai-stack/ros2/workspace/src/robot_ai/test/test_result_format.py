from robot_ai.result_format import segments_to_list


class BBox:
    def __init__(self, cx, cy, w, h):
        self.center_x = cx
        self.center_y = cy
        self.size_x = w
        self.size_y = h
        self.theta = 0.0


class Pt:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Poly:
    def __init__(self, pts):
        self.points = [Pt(x, y) for x, y in pts]


class Seg:
    def __init__(self, cls, score, cx, cy, w, h, pts=()):
        self.class_name = cls
        self.score = score
        self.bbox = BBox(cx, cy, w, h)
        self.polygon = Poly(pts)


class Arr:
    def __init__(self, segments):
        self.segments = segments


def test_converts_center_size_to_xyxy():
    out = segments_to_list(Arr([Seg("grass", 0.9, 100, 200, 40, 60)]))
    assert out == [{
        "class_name": "grass", "score": 0.9,
        "bbox_xyxy": [80.0, 170.0, 120.0, 230.0],
        "bbox_center": [100.0, 200.0], "bbox_size": [40.0, 60.0],
        "polygon": [],
    }]


def test_empty_segments():
    assert segments_to_list(Arr([])) == []


def test_polygon_mapped():
    out = segments_to_list(Arr([Seg("grass", 0.5, 10, 10, 2, 2, pts=[(1, 2), (3, 4)])]))
    assert out[0]["polygon"] == [[1.0, 2.0], [3.0, 4.0]]
