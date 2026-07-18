from robot_ai.image_queue import ImageFileQueue


def test_queues_each_new_file_once(tmp_path):
    (tmp_path / "frame.jpg").write_bytes(b"first")
    queue = ImageFileQueue(str(tmp_path))

    queue.refresh()
    item = queue.pop()
    assert item is not None
    queue.mark_processed(*item)

    queue.refresh()
    assert queue.pop() is None


def test_queues_updated_file_again(tmp_path):
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"first")
    queue = ImageFileQueue(str(tmp_path))
    queue.refresh()
    item = queue.pop()
    assert item is not None
    queue.mark_processed(*item)

    image.write_bytes(b"updated-content")
    queue.refresh()
    updated = queue.pop()
    assert updated is not None
    assert updated[0] == "frame.jpg"


def test_ignores_temporary_and_non_image_files(tmp_path):
    (tmp_path / "frame.jpg.part").write_bytes(b"incomplete")
    (tmp_path / "notes.txt").write_text("ignore")
    queue = ImageFileQueue(str(tmp_path))

    queue.refresh()
    assert queue.pop() is None
