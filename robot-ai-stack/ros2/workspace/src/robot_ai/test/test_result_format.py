from robot_ai.result_format import detections_to_list


class P:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Center:
    def __init__(self, x, y):
        self.position = P(x, y)


class BBox:
    def __init__(self, cx, cy, w, h):
        self.center = Center(cx, cy)
        self.size_x = w
        self.size_y = h


class Hyp:
    def __init__(self, c, s):
        self.class_id = c
        self.score = s


class Res:
    def __init__(self, c, s):
        self.hypothesis = Hyp(c, s)


class Det:
    def __init__(self, cx, cy, w, h, c, s):
        self.bbox = BBox(cx, cy, w, h)
        self.results = [Res(c, s)]


class Arr:
    def __init__(self, dets):
        self.detections = dets


def test_converts_center_size_to_xyxy():
    out = detections_to_list(Arr([Det(100, 200, 40, 60, "grass", 0.9)]))
    assert out == [{
        "class_name": "grass", "score": 0.9,
        "bbox_xyxy": [80.0, 170.0, 120.0, 230.0],
        "bbox_center": [100.0, 200.0], "bbox_size": [40.0, 60.0],
    }]


def test_empty_detections():
    assert detections_to_list(Arr([])) == []


def test_missing_results_defaults():
    d = Det(10, 10, 2, 2, "x", 0.5)
    d.results = []
    out = detections_to_list(Arr([d]))
    assert out[0]["class_name"] == "" and out[0]["score"] == 0.0
