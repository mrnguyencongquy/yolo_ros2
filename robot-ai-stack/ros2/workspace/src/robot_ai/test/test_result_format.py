from robot_ai.result_format import segments_to_list


class BBox:
    def __init__(self, cx, cy, w, h):
        self.center_x = cx
        self.center_y = cy
        self.size_x = w
        self.size_y = h
        self.theta = 0.0


class Pt:
    def __init__(self, x, y, z=0.0):
        self.x = x
        self.y = y
        self.z = z


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


def test_converts_segment_to_output_contract():
    out = segments_to_list(Arr([Seg("grass", 0.9, 100, 200, 40, 60)]))
    assert out == [{
        "class_name": "grass", "score": 0.9,
        "bbox": {
            "center_x": 100.0, "center_y": 200.0,
            "size_x": 40.0, "size_y": 60.0, "theta": 0.0,
        },
        "polygon": {"points": []},
    }]


def test_empty_segments():
    assert segments_to_list(Arr([])) == []


def test_polygon_mapped():
    out = segments_to_list(Arr([Seg("grass", 0.5, 10, 10, 2, 2, pts=[(1, 2), (3, 4)])]))
    assert out[0]["polygon"]["points"] == [
        {"x": 1.0, "y": 2.0, "z": 0.0},
        {"x": 3.0, "y": 4.0, "z": 0.0},
    ]
