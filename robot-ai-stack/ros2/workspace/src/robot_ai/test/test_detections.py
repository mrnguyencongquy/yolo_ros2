import json

from robot_ai.detections import parse_detections


def test_valid_list():
    raw = json.dumps([{"class_id": 0, "class_name": "grass", "confidence": 0.9, "bbox": [1, 2, 3, 4]}]).encode()
    out = parse_detections(raw)
    assert out == [{"class_id": 0, "class_name": "grass", "confidence": 0.9, "bbox": [1.0, 2.0, 3.0, 4.0]}]


def test_bad_json_returns_empty():             # TC-43
    assert parse_detections(b"not-json") == []


def test_drops_detection_missing_bbox():       # TC-06
    raw = json.dumps([{"class_name": "grass"}, {"class_id": 1, "class_name": "g", "confidence": 0.5, "bbox": [0, 0, 1, 1]}]).encode()
    out = parse_detections(raw)
    assert len(out) == 1 and out[0]["class_id"] == 1


def test_non_list_returns_empty():
    assert parse_detections(json.dumps({"a": 1}).encode()) == []
