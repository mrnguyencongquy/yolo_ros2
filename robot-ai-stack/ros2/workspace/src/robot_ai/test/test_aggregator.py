from robot_ai.aggregator import DetectionAggregator


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def det(name):
    return {"class_name": name, "bbox": [0, 0, 1, 1]}


def test_complete_emits_once_and_clears():     # TC-14, TC-36
    agg = DetectionAggregator(timeout_s=10)
    assert agg.add("A", 0, 2, [det("g1")]) is None
    out = agg.add("A", 1, 2, [det("g2")])
    assert out is not None and len(out) == 2
    assert agg.add("A", 0, 2, [det("x")]) is None   # late after emit ignored


def test_num_tiles_one_immediate():            # TC-16, TC-57
    agg = DetectionAggregator()
    assert agg.add("A", 0, 1, [det("g")]) is not None


def test_all_empty_emits_empty_list():         # TC-20
    agg = DetectionAggregator()
    agg.add("A", 0, 2, [])
    out = agg.add("A", 1, 2, [])
    assert out == []


def test_out_of_order():                       # TC-33
    agg = DetectionAggregator()
    assert agg.add("A", 1, 2, [det("a")]) is None
    assert agg.add("A", 0, 2, [det("b")]) is not None


def test_duplicate_tile_ignored():             # TC-34
    agg = DetectionAggregator()
    assert agg.add("A", 0, 2, [det("a")]) is None
    assert agg.add("A", 0, 2, [det("dup")]) is None
    assert agg.add("A", 1, 2, [det("b")]) is not None


def test_invalid_num_tiles():                  # TC-05
    agg = DetectionAggregator()
    assert agg.add("A", 0, 0, [det("a")]) is None


def test_independent_buffers():                # TC-35
    agg = DetectionAggregator()
    agg.add("A", 0, 2, [det("a")])
    agg.add("B", 0, 2, [det("b")])
    assert agg.add("A", 1, 2, [det("a2")]) is not None
    assert agg.add("B", 1, 2, [det("b2")]) is not None


def test_flush_expired():                      # TC-15, TC-42
    clk = Clock()
    agg = DetectionAggregator(timeout_s=2.0, clock=clk)
    agg.add("A", 0, 3, [det("a")])
    clk.t = 1.0
    assert agg.flush_expired() == []
    clk.t = 2.5
    flushed = agg.flush_expired()
    assert len(flushed) == 1 and flushed[0][0] == "A"
    assert agg.flush_expired() == []


def test_deterministic_order():                # TC-50
    agg = DetectionAggregator()
    agg.add("A", 0, 2, [det("a")])
    out = agg.add("A", 1, 2, [det("b")])
    assert [d["class_name"] for d in out] == ["a", "b"]
