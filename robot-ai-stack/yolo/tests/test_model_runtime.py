from app.yolo_server import _model_revision, _truthy


def test_truthy_values():
    assert _truthy("true")
    assert _truthy("1")
    assert not _truthy("0")


def test_model_revision_tracks_file_changes(tmp_path):
    model = tmp_path / "model.pt"
    model.write_bytes(b"v1")
    first = _model_revision(str(model))

    model.write_bytes(b"version-two")
    second = _model_revision(str(model))

    assert first is not None
    assert second is not None
    assert first != second


def test_model_revision_returns_none_when_missing(tmp_path):
    assert _model_revision(str(tmp_path / "missing.pt")) is None
