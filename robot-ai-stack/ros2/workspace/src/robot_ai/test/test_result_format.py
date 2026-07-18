from robot_ai.result_format import instances_to_list


class BBox:
    def __init__(self, cx, cy, w, h):
        self.center_x = cx
        self.center_y = cy
        self.size_x = w
        self.size_y = h


class Pt:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Poly:
    def __init__(self, pts):
        self.points = [Pt(x, y) for x, y in pts]


class Instance:
    def __init__(self, cls, score, cx, cy, w, h, pts=()):
        self.class_name = cls
        self.score = score
        self.bbox = BBox(cx, cy, w, h)
        self.polygon = Poly(pts)


class Arr:
    def __init__(self, instances):
        self.instances = instances


def test_converts_instance_to_output_contract():
    out = instances_to_list(Arr([Instance("target_class", 0.9, 100, 200, 40, 60)]))
    assert out == [{
        "class_name": "target_class", "score": 0.9,
        "bbox": {
            "center_x": 100.0, "center_y": 200.0,
            "size_x": 40.0, "size_y": 60.0,
        },
        "polygon": {"points": []},
    }]


def test_empty_instances():
    assert instances_to_list(Arr([])) == []


def test_polygon_mapped():
    out = instances_to_list(
        Arr([Instance("target_class", 0.5, 10, 10, 2, 2, pts=[(1, 2), (3, 4)])])
    )
    assert out[0]["polygon"]["points"] == [
        {"x": 1.0, "y": 2.0},
        {"x": 3.0, "y": 4.0},
    ]
