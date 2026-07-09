import cv2
import numpy as np

from app.inference import decode_jpeg, run_inference


def _jpeg():
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    return cv2.imencode(".jpg", img)[1].tobytes()


class FakeBox:
    def __init__(self, cls, conf, xyxy):
        self.cls = [cls]
        self.conf = [conf]
        self.xyxy = [xyxy]


class FakeResult:
    def __init__(self, boxes, masks=None):
        self.boxes = boxes
        self.masks = masks


class FakeMasks:
    def __init__(self, xy):
        self.xy = xy


class FakeModel:
    names = {0: "grass", 1: "tree"}

    def __init__(self, boxes, masks=None):
        self._boxes = boxes
        self._masks = masks

    def __call__(self, img, verbose=False):
        return [FakeResult(self._boxes, self._masks)]


def test_decode_bad_returns_none():            # TC-03
    assert decode_jpeg(b"not-jpeg") is None


def test_decode_empty_returns_none():          # TC-04
    assert decode_jpeg(b"") is None


def test_decode_valid_roundtrip():
    assert decode_jpeg(_jpeg()).shape == (32, 32, 3)


def test_run_none_image_returns_empty():
    assert run_inference(FakeModel([]), None) == []


def test_multiple_detections():                # TC-27
    m = FakeModel([FakeBox(0, 0.9, [1, 2, 3, 4]), FakeBox(1, 0.8, [5, 6, 7, 8])])
    out = run_inference(m, np.zeros((8, 8, 3), np.uint8))
    assert len(out) == 2 and out[0]["class_name"] == "grass"


def test_single_detection():                   # TC-28
    m = FakeModel([FakeBox(0, 0.5, [0, 0, 1, 1])])
    assert len(run_inference(m, np.zeros((8, 8, 3), np.uint8))) == 1


def test_target_class_filter():                # TC-31
    m = FakeModel([FakeBox(0, 0.9, [1, 1, 2, 2]), FakeBox(1, 0.9, [3, 3, 4, 4])])
    out = run_inference(m, np.zeros((8, 8, 3), np.uint8), target_classes={"grass"})
    assert len(out) == 1 and out[0]["class_name"] == "grass"


def test_segmentation_polygon():
    masks = FakeMasks([np.array([[1, 2], [3, 4]], dtype=np.float32)])
    m = FakeModel([FakeBox(0, 0.9, [1, 2, 3, 4])], masks=masks)
    out = run_inference(m, np.zeros((8, 8, 3), np.uint8))
    assert out[0]["polygon"] == [[1.0, 2.0], [3.0, 4.0]]
