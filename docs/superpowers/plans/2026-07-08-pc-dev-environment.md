# PC Dev Environment + Tiling Pipeline + YOLO/ROS2 Decoupling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng bản chạy dev-first trên PC x86 (RTX 3060) cho `robot-ai-stack`, tách YOLO khỏi ROS2 qua ZeroMQ, và xử lý pipeline tile→detect→toạ độ 4K, giữ khả năng build song song cho Jetson.

**Architecture:** Compose override (`docker-compose.yml` + `.pc.yml`/`.jetson.yml`) chọn base image + GPU theo nền tảng. Logic thuần (transform toạ độ, tiling, aggregate, parse) tách thành module Python không phụ thuộc ROS2 để test bằng pytest trên host. `yolo_server` (ZeroMQ REP, không ROS2) chạy inference; node ROS2 `yolo_bridge` cộng offset LOCAL→GLOBAL + gom theo `image_id` → publish `vision_msgs/Detection2DArray`; `sample_publisher` đọc ảnh từ folder thay tiler bên thứ 3.

**Tech Stack:** ROS2 Jazzy, Docker Compose v5, ZeroMQ (pyzmq), Ultralytics YOLO, PyTorch CUDA, OpenCV, pytest, colcon.

Source spec: `docs/superpowers/specs/2026-07-07-pc-dev-environment-design.md`
Test spec: `docs/superpowers/test-specs/2026-07-07-pc-dev-environment.md` (case ids TC-xx referenced below)

---

## File Structure

**Create:**
- `.gitignore`, `README.md`
- `robot-ai-stack/docker-compose.pc.yml`, `docker-compose.jetson.yml`, `env.pc.example`, `env.jetson.example`
- `robot-ai-stack/ros2/workspace/src/robot_ai_interfaces/` (msg/TileImage.msg, package.xml, CMakeLists.txt)
- `robot-ai-stack/ros2/workspace/src/robot_ai/robot_ai/geometry.py` — transform/clamp bbox (pure)
- `.../robot_ai/tiling.py` — grid split (pure)
- `.../robot_ai/detections.py` — parse server JSON (pure)
- `.../robot_ai/aggregator.py` — gom theo image_id (pure)
- `.../robot_ai/zmq_client.py` — ZeroMQ REQ client + recreate-on-timeout
- `.../robot_ai/sample_publisher.py` — node đọc folder → TileImage
- `.../robot_ai/yolo_bridge.py` — node ZMQ + transform + aggregate → Detection2DArray
- `.../robot_ai/detection_msg.py` — build vision_msgs.Detection2DArray (ROS2)
- `.../robot_ai/test/` — pytest cho các module thuần
- `robot-ai-stack/yolo/app/inference.py` — decode + run_inference (pure-ish)
- `robot-ai-stack/yolo/app/yolo_server.py` — ZeroMQ REP loop
- `robot-ai-stack/yolo/Dockerfile.pc`
- `robot-ai-stack/yolo/tests/` — pytest cho inference

**Modify:**
- `robot-ai-stack/docker-compose.yml` — rút gọn còn phần chung
- `robot-ai-stack/yolo/Dockerfile` → rename `Dockerfile.jetson` (+ pyzmq)
- `robot-ai-stack/yolo/requirements.txt` — thêm `pyzmq`
- `robot-ai-stack/ros2/Dockerfile` — thêm `pyzmq`, `ros-jazzy-vision-msgs`
- `.../robot_ai/setup.py`, `package.xml` — entry points + deps
- `.../robot_ai/launch/robot_ai.launch.py` — chạy 2 node

**Delete:** `.../robot_ai/robot_ai/image_publisher.py`, `robot-ai-stack/yolo/app/detector.py`

---

## Task 1: Repo scaffolding + git init

**Files:**
- Create: `.gitignore`, `README.md`

- [ ] **Step 1: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/

# ROS2 colcon
build/
install/
log/

# Env (per-machine platform selection)
.env

# Docker/IDE
*.log
.vscode/
```

- [ ] **Step 2: Write `README.md`**

```markdown
# yolo_ros2 — Grass detection AI stack

ROS2 Jazzy + YOLO (Ultralytics) tiling detection pipeline. Dev trên PC x86 (CUDA), verify trên Jetson.

## Chạy
```bash
cd robot-ai-stack
cp env.pc.example .env        # PC   (hoặc env.jetson.example trên Jetson)
docker compose up --build
```
Xem `docs/superpowers/specs/` cho thiết kế, `docs/superpowers/plans/` cho kế hoạch.
```

- [ ] **Step 3: Init git + first commit**

Run:
```bash
cd /media/congquy/ss870_v0/vizo_870/GrassRobot/Grass_Robot
git init
git add .gitignore README.md docs/ "robot ai stack.txt" robot-ai-stack/
git commit -m "chore: scaffold repo + design/test-spec/plan docs"
```
Expected: repo created, 1 commit. (Push lên GitHub do bạn tự làm: `git remote add origin git@github.com:mrnguyencongquy/yolo_ros2.git && git push -u origin main`.)

---

## Task 2: `robot_ai_interfaces` package + `TileImage.msg`

**Files:**
- Create: `robot-ai-stack/ros2/workspace/src/robot_ai_interfaces/msg/TileImage.msg`
- Create: `.../robot_ai_interfaces/package.xml`
- Create: `.../robot_ai_interfaces/CMakeLists.txt`

- [ ] **Step 1: Write `msg/TileImage.msg`** (TC-47, R8)

```
std_msgs/Header header
string image_id
uint16 tile_index
uint16 tile_row
uint16 tile_col
uint16 num_tiles
uint32 x_offset
uint32 y_offset
uint32 tile_width
uint32 tile_height
uint32 orig_width
uint32 orig_height
sensor_msgs/Image image
```

- [ ] **Step 2: Write `package.xml`**

```xml
<?xml version="1.0"?>
<package format="3">
  <name>robot_ai_interfaces</name>
  <version>0.1.0</version>
  <description>Custom messages for grass-detection tiling pipeline</description>
  <maintainer email="dev3@vizo.co.jp">vizo</maintainer>
  <license>Proprietary</license>

  <buildtool_depend>ament_cmake</buildtool_depend>
  <buildtool_depend>rosidl_default_generators</buildtool_depend>

  <depend>std_msgs</depend>
  <depend>sensor_msgs</depend>

  <exec_depend>rosidl_default_runtime</exec_depend>
  <member_of_group>rosidl_interface_packages</member_of_group>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
```

- [ ] **Step 3: Write `CMakeLists.txt`**

```cmake
cmake_minimum_required(VERSION 3.8)
project(robot_ai_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/TileImage.msg"
  DEPENDENCIES std_msgs sensor_msgs
)

ament_package()
```

- [ ] **Step 4: Build & verify the message compiles** (TC-47)

Run (inside ros2 container or a ROS2 Jazzy env):
```bash
cd robot-ai-stack/ros2/workspace
colcon build --packages-select robot_ai_interfaces
source install/setup.bash
python3 -c "from robot_ai_interfaces.msg import TileImage; print('OK', TileImage.__slots__)"
```
Expected: `OK [...]` listing the fields.

- [ ] **Step 5: Commit**

```bash
git add robot-ai-stack/ros2/workspace/src/robot_ai_interfaces
git commit -m "feat(interfaces): add TileImage message"
```

---

## Task 3: `geometry.py` — LOCAL→GLOBAL transform (pure, TDD)

**Files:**
- Create: `.../robot_ai/robot_ai/geometry.py`
- Test: `.../robot_ai/test/test_geometry.py`

- [ ] **Step 1: Write failing tests** (TC-56, TC-01, TC-02, TC-10, TC-11, TC-12, TC-25, TC-38)

```python
# test/test_geometry.py
from robot_ai.geometry import BBox, normalize_bbox, local_to_global

def test_happy_shift():                       # TC-56
    g = local_to_global(BBox(10,20,50,60), 960, 720, 3840, 2160)
    assert (g.x1,g.y1,g.x2,g.y2) == (970,740,1010,780)

def test_inverted_bbox_normalized():          # TC-01
    assert normalize_bbox(BBox(50,60,10,20)) == BBox(10,20,50,60)

def test_negative_clamped_to_zero():          # TC-02
    g = local_to_global(BBox(-5,-5,10,10), 0, 0, 3840, 2160)
    assert (g.x1,g.y1) == (0,0)

def test_edge_equals_orig_no_extra_clamp():   # TC-10
    g = local_to_global(BBox(0,0,960,720), 2880, 1440, 3840, 2160)
    assert (g.x2,g.y2) == (3840,2160)

def test_just_outside_clamped():              # TC-11
    g = local_to_global(BBox(0,0,961,0), 2880, 0, 3840, 2160)
    assert g.x2 == 3840

def test_far_corner_tile():                   # TC-12
    g = local_to_global(BBox(959,719,960,720), 2880, 1440, 3840, 2160)
    assert (g.x2,g.y2) == (3840,2160)

def test_pure_idempotent():                   # TC-38
    args = (BBox(1,2,3,4), 10, 20, 100, 100)
    assert local_to_global(*args) == local_to_global(*args)
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest robot-ai-stack/ros2/workspace/src/robot_ai/test/test_geometry.py -v`
Expected: FAIL — `ModuleNotFoundError: robot_ai.geometry`.

- [ ] **Step 3: Implement `geometry.py`**

```python
# robot_ai/geometry.py
from dataclasses import dataclass

@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

def normalize_bbox(b: BBox) -> BBox:
    """Đảm bảo x1<=x2, y1<=y2 (bbox có thể bị đảo từ model)."""
    return BBox(min(b.x1, b.x2), min(b.y1, b.y2), max(b.x1, b.x2), max(b.y1, b.y2))

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(v, hi))

def local_to_global(b: BBox, x_offset: int, y_offset: int, orig_w: int, orig_h: int) -> BBox:
    """Dời bbox toạ độ tile → toạ độ ảnh gốc, clamp về [0..orig]."""
    b = normalize_bbox(b)
    return BBox(
        _clamp(b.x1 + x_offset, 0, orig_w),
        _clamp(b.y1 + y_offset, 0, orig_h),
        _clamp(b.x2 + x_offset, 0, orig_w),
        _clamp(b.y2 + y_offset, 0, orig_h),
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest robot-ai-stack/ros2/workspace/src/robot_ai/test/test_geometry.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add robot-ai-stack/ros2/workspace/src/robot_ai/robot_ai/geometry.py robot-ai-stack/ros2/workspace/src/robot_ai/test/test_geometry.py
git commit -m "feat(robot_ai): local->global bbox transform with clamp"
```

---

## Task 4: `tiling.py` — grid split (pure, TDD)

**Files:**
- Create: `.../robot_ai/robot_ai/tiling.py`
- Test: `.../robot_ai/test/test_tiling.py`

- [ ] **Step 1: Write failing tests** (TC-17, TC-18, TC-51)

```python
# test/test_tiling.py
import numpy as np
from robot_ai.tiling import compute_tiles, split_image

def test_4x3_exact():                          # TC-17
    tiles = compute_tiles(3840, 2160, 4, 3)
    assert len(tiles) == 12
    assert (tiles[0].x_offset, tiles[0].y_offset) == (0, 0)
    assert (tiles[0].width, tiles[0].height) == (960, 720)
    assert (tiles[-1].x_offset, tiles[-1].y_offset) == (2880, 1440)

def test_remainder_in_last():                  # TC-18
    tiles = compute_tiles(3841, 2161, 4, 3)
    assert tiles[-1].width == 3841 - 2880       # 961
    assert tiles[-1].height == 2161 - 1440      # 721
    # phủ hết, không hở: tổng chiều rộng hàng đầu == orig_w
    row0 = [t for t in tiles if t.row == 0]
    assert sum(t.width for t in row0) == 3841

def test_split_image_shapes_and_deterministic():  # TC-51
    img = np.zeros((2160, 3840, 3), dtype=np.uint8)
    a = split_image(img, 4, 3)
    b = split_image(img, 4, 3)
    assert len(a) == 12
    spec, tile = a[0]
    assert tile.shape == (720, 960, 3)
    assert [s.__dict__ for s,_ in a] == [s.__dict__ for s,_ in b]
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest robot-ai-stack/ros2/workspace/src/robot_ai/test/test_tiling.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `tiling.py`**

```python
# robot_ai/tiling.py
from dataclasses import dataclass

@dataclass(frozen=True)
class TileSpec:
    index: int
    row: int
    col: int
    x_offset: int
    y_offset: int
    width: int
    height: int

def compute_tiles(orig_w: int, orig_h: int, cols: int, rows: int) -> list[TileSpec]:
    """Chia lưới; cột/hàng cuối gánh phần dư → phủ hết, không overlap."""
    base_w, base_h = orig_w // cols, orig_h // rows
    tiles, idx = [], 0
    for r in range(rows):
        for c in range(cols):
            x, y = c * base_w, r * base_h
            w = base_w if c < cols - 1 else orig_w - x
            h = base_h if r < rows - 1 else orig_h - y
            tiles.append(TileSpec(idx, r, c, x, y, w, h))
            idx += 1
    return tiles

def split_image(img, cols: int, rows: int):
    """Trả list (TileSpec, ndarray tile)."""
    h, w = img.shape[:2]
    return [
        (s, img[s.y_offset:s.y_offset + s.height, s.x_offset:s.x_offset + s.width])
        for s in compute_tiles(w, h, cols, rows)
    ]
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest robot-ai-stack/ros2/workspace/src/robot_ai/test/test_tiling.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add robot-ai-stack/ros2/workspace/src/robot_ai/robot_ai/tiling.py robot-ai-stack/ros2/workspace/src/robot_ai/test/test_tiling.py
git commit -m "feat(robot_ai): grid tiling split with remainder handling"
```

---

## Task 5: `detections.py` — parse server JSON (pure, TDD)

**Files:**
- Create: `.../robot_ai/robot_ai/detections.py`
- Test: `.../robot_ai/test/test_detections.py`

- [ ] **Step 1: Write failing tests** (TC-06, TC-43)

```python
# test/test_detections.py
import json
from robot_ai.detections import parse_detections

def test_valid_list():
    raw = json.dumps([{"class_id":0,"class_name":"grass","confidence":0.9,"bbox":[1,2,3,4]}]).encode()
    out = parse_detections(raw)
    assert out == [{"class_id":0,"class_name":"grass","confidence":0.9,"bbox":[1.0,2.0,3.0,4.0]}]

def test_bad_json_returns_empty():             # TC-43
    assert parse_detections(b"not-json") == []

def test_drops_detection_missing_bbox():       # TC-06
    raw = json.dumps([{"class_name":"grass"}, {"class_id":1,"class_name":"g","confidence":0.5,"bbox":[0,0,1,1]}]).encode()
    out = parse_detections(raw)
    assert len(out) == 1 and out[0]["class_id"] == 1

def test_non_list_returns_empty():
    assert parse_detections(json.dumps({"a":1}).encode()) == []
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest robot-ai-stack/ros2/workspace/src/robot_ai/test/test_detections.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `detections.py`**

```python
# robot_ai/detections.py
import json

def parse_detections(raw: bytes) -> list[dict]:
    """Parse reply JSON của yolo_server. Bỏ detection méo mó, trả [] nếu JSON hỏng."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for d in data:
        if not isinstance(d, dict):
            continue
        bbox = d.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        try:
            out.append({
                "class_id": int(d.get("class_id", -1)),
                "class_name": str(d.get("class_name", "")),
                "confidence": float(d.get("confidence", 0.0)),
                "bbox": [float(v) for v in bbox],
            })
        except (TypeError, ValueError):
            continue
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest robot-ai-stack/ros2/workspace/src/robot_ai/test/test_detections.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add robot-ai-stack/ros2/workspace/src/robot_ai/robot_ai/detections.py robot-ai-stack/ros2/workspace/src/robot_ai/test/test_detections.py
git commit -m "feat(robot_ai): robust server-reply detection parser"
```

---

## Task 6: `aggregator.py` — gom theo image_id (pure, TDD)

**Files:**
- Create: `.../robot_ai/robot_ai/aggregator.py`
- Test: `.../robot_ai/test/test_aggregator.py`

- [ ] **Step 1: Write failing tests** (TC-05, TC-14, TC-15, TC-16, TC-19, TC-20, TC-33, TC-34, TC-35, TC-36, TC-42, TC-50, TC-57)

```python
# test/test_aggregator.py
from robot_ai.aggregator import DetectionAggregator

class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t

def det(name): return {"class_name": name, "bbox":[0,0,1,1]}

def test_complete_emits_once_and_clears():     # TC-14
    agg = DetectionAggregator(timeout_s=10)
    assert agg.add("A", 0, 2, [det("g1")]) is None
    out = agg.add("A", 1, 2, [det("g2")])
    assert out is not None and len(out) == 2   # TC-19 empty tile still counts below
    assert agg.add("A", 0, 2, [det("x")]) is None  # TC-36 late after emit ignored

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
    assert agg.add("A", 0, 2, [det("dup")]) is None   # dup, not counted
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
    assert agg.flush_expired() == []           # buffer cleaned, no leak

def test_deterministic_order():                # TC-50
    agg = DetectionAggregator()
    agg.add("A", 0, 2, [det("a")])
    out = agg.add("A", 1, 2, [det("b")])
    assert [d["class_name"] for d in out] == ["a", "b"]
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest robot-ai-stack/ros2/workspace/src/robot_ai/test/test_aggregator.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `aggregator.py`**

```python
# robot_ai/aggregator.py
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

@dataclass
class _Buffer:
    num_tiles: int
    created: float
    seen: set = field(default_factory=set)
    detections: list = field(default_factory=list)

class DetectionAggregator:
    """Gom detections của các tile cùng image_id đến khi đủ num_tiles hoặc timeout."""

    def __init__(self, timeout_s: float = 2.0, clock: Optional[Callable[[], float]] = None, done_cap: int = 1024):
        self._timeout = timeout_s
        self._clock = clock or time.monotonic
        self._buffers: dict[str, _Buffer] = {}
        self._done: set = set()
        self._done_order: deque = deque(maxlen=done_cap)

    def _mark_done(self, image_id: str) -> None:
        if len(self._done_order) == self._done_order.maxlen:
            self._done.discard(self._done_order[0])
        self._done_order.append(image_id)
        self._done.add(image_id)

    def add(self, image_id: str, tile_index: int, num_tiles: int, dets: list) -> Optional[list]:
        """Thêm 1 tile. Trả list gộp khi đủ tile, ngược lại None."""
        if num_tiles <= 0 or image_id in self._done:
            return None
        buf = self._buffers.get(image_id)
        if buf is None:
            buf = _Buffer(num_tiles=num_tiles, created=self._clock())
            self._buffers[image_id] = buf
        if tile_index in buf.seen:
            return None
        buf.seen.add(tile_index)
        buf.detections.extend(dets)
        if len(buf.seen) >= buf.num_tiles:
            self._mark_done(image_id)
            return self._buffers.pop(image_id).detections
        return None

    def flush_expired(self) -> list:
        """Trả [(image_id, detections)] cho buffer quá timeout; dọn buffer."""
        now = self._clock()
        out = []
        for image_id in list(self._buffers):
            if now - self._buffers[image_id].created >= self._timeout:
                self._mark_done(image_id)
                out.append((image_id, self._buffers.pop(image_id).detections))
        return out
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest robot-ai-stack/ros2/workspace/src/robot_ai/test/test_aggregator.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add robot-ai-stack/ros2/workspace/src/robot_ai/robot_ai/aggregator.py robot-ai-stack/ros2/workspace/src/robot_ai/test/test_aggregator.py
git commit -m "feat(robot_ai): image_id detection aggregator with timeout flush"
```

---

## Task 7: `yolo/app/inference.py` — decode + run_inference (TDD)

**Files:**
- Create: `robot-ai-stack/yolo/app/inference.py`
- Test: `robot-ai-stack/yolo/tests/test_inference.py`

- [ ] **Step 1: Write failing tests** (TC-03, TC-04, TC-27, TC-28, TC-31)

```python
# tests/test_inference.py
import cv2, numpy as np
from app.inference import decode_jpeg, run_inference

def _jpeg():
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    return cv2.imencode(".jpg", img)[1].tobytes()

class FakeBox:
    def __init__(self, cls, conf, xyxy): self.cls=[cls]; self.conf=[conf]; self.xyxy=[xyxy]
class FakeResult:
    def __init__(self, boxes): self.boxes=boxes
class FakeModel:
    names = {0: "grass", 1: "tree"}
    def __init__(self, boxes): self._boxes=boxes
    def __call__(self, img, verbose=False): return [FakeResult(self._boxes)]

def test_decode_bad_returns_none():            # TC-03
    assert decode_jpeg(b"not-jpeg") is None

def test_decode_empty_returns_none():          # TC-04
    assert decode_jpeg(b"") is None

def test_run_none_image_returns_empty():       # TC-03/04 downstream
    assert run_inference(FakeModel([]), None) == []

def test_multiple_detections():               # TC-27
    m = FakeModel([FakeBox(0,0.9,[1,2,3,4]), FakeBox(1,0.8,[5,6,7,8])])
    out = run_inference(m, np.zeros((8,8,3), np.uint8))
    assert len(out) == 2 and out[0]["class_name"] == "grass"

def test_single_detection():                  # TC-28
    m = FakeModel([FakeBox(0,0.5,[0,0,1,1])])
    assert len(run_inference(m, np.zeros((8,8,3), np.uint8))) == 1

def test_target_class_filter():               # TC-31
    m = FakeModel([FakeBox(0,0.9,[1,1,2,2]), FakeBox(1,0.9,[3,3,4,4])])
    out = run_inference(m, np.zeros((8,8,3), np.uint8), target_classes={"grass"})
    assert len(out) == 1 and out[0]["class_name"] == "grass"
```

- [ ] **Step 2: Run to verify fail**

Run: `cd robot-ai-stack/yolo && pytest tests/test_inference.py -v`
Expected: FAIL — `ModuleNotFoundError: app.inference`.

- [ ] **Step 3: Implement `app/inference.py`**

```python
# app/inference.py
import cv2
import numpy as np

def decode_jpeg(data: bytes):
    """Giải mã JPEG → BGR ndarray; None nếu rỗng/hỏng."""
    if not data:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def run_inference(model, img, target_classes=None) -> list[dict]:
    """Chạy YOLO trên ảnh BGR → list detection toạ độ LOCAL (trong tile)."""
    if img is None:
        return []
    dets = []
    for r in model(img, verbose=False):
        for box in r.boxes:
            cls = int(box.cls[0])
            name = model.names[cls]
            if target_classes and name not in target_classes:
                continue
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
            dets.append({
                "class_id": cls,
                "class_name": name,
                "confidence": float(box.conf[0]),
                "bbox": [x1, y1, x2, y2],
            })
    return dets
```

- [ ] **Step 4: Run to verify pass**

Run: `cd robot-ai-stack/yolo && pytest tests/test_inference.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add robot-ai-stack/yolo/app/inference.py robot-ai-stack/yolo/tests/test_inference.py
git commit -m "feat(yolo): testable jpeg decode + inference wrapper"
```

---

## Task 8: `yolo/app/yolo_server.py` — ZeroMQ REP loop

**Files:**
- Create: `robot-ai-stack/yolo/app/yolo_server.py`
- Modify: `robot-ai-stack/yolo/requirements.txt`
- Delete: `robot-ai-stack/yolo/app/detector.py`
- Test: `robot-ai-stack/yolo/tests/test_server_config.py`

- [ ] **Step 1: Write failing test for config/import guards** (TC-09, TC-48)

```python
# tests/test_server_config.py
import subprocess, sys, os

def test_invalid_port_exits_nonzero():         # TC-09
    env = dict(os.environ, YOLO_ZMQ_PORT="abc", YOLO_MODEL="/nonexistent.pt")
    p = subprocess.run([sys.executable, "app/yolo_server.py"], env=env,
                       capture_output=True, text=True, cwd=os.getcwd())
    assert p.returncode == 2

def test_module_imports_without_ros2():        # TC-48
    # yolo_server chỉ được import zmq/cv2/ultralytics/torch — KHÔNG rclpy/cv_bridge
    src = open("app/yolo_server.py").read()
    assert "rclpy" not in src and "cv_bridge" not in src
```

- [ ] **Step 2: Run to verify fail**

Run: `cd robot-ai-stack/yolo && pytest tests/test_server_config.py -v`
Expected: FAIL — file `app/yolo_server.py` missing.

- [ ] **Step 3: Implement `app/yolo_server.py`**

```python
# app/yolo_server.py
import json
import os
import sys

def _get_port() -> int:
    raw = os.environ.get("YOLO_ZMQ_PORT", "5555")
    try:
        return int(raw)
    except ValueError:
        print(f"[yolo_server] invalid YOLO_ZMQ_PORT: {raw!r}", file=sys.stderr)
        sys.exit(2)

def main() -> None:
    port = _get_port()
    model_path = os.environ.get("YOLO_MODEL", "/app/models/yolo26n.pt")
    if not os.path.exists(model_path):
        print(f"[yolo_server] model not found: {model_path}", file=sys.stderr)
        sys.exit(3)

    import torch
    import zmq
    from ultralytics import YOLO
    from app.inference import decode_jpeg, run_inference

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[yolo_server] device={device} model={model_path}", flush=True)
    model = YOLO(model_path)
    raw_targets = os.environ.get("YOLO_TARGET_CLASSES")
    targets = {t.strip() for t in raw_targets.split(",")} if raw_targets else None

    ctx = zmq.Context()
    sock = ctx.socket(zmq.REP)
    sock.bind(f"tcp://*:{port}")
    print(f"[yolo_server] listening on tcp://*:{port}", flush=True)
    while True:
        data = sock.recv()
        dets = run_inference(model, decode_jpeg(data), targets)
        sock.send_string(json.dumps(dets))

if __name__ == "__main__":
    main()
```

`_get_port` and the model-path check run before importing torch, so TC-09 exits fast without heavy imports.

- [ ] **Step 4: Add `pyzmq` to `requirements.txt`**

```
ultralytics
opencv-python
numpy
pyzmq
```

- [ ] **Step 5: Delete old `detector.py`**

Run: `git rm robot-ai-stack/yolo/app/detector.py`

- [ ] **Step 6: Run to verify pass**

Run: `cd robot-ai-stack/yolo && pytest tests/test_server_config.py -v`
Expected: 2 passed. (Needs `torch`/`ultralytics`/`zmq` NOT imported for these tests — guaranteed by early exits.)

- [ ] **Step 7: Commit**

```bash
git add robot-ai-stack/yolo/app/yolo_server.py robot-ai-stack/yolo/requirements.txt robot-ai-stack/yolo/tests/test_server_config.py
git commit -m "feat(yolo): ZeroMQ REP server, drop ROS2 dependency"
```

---

## Task 9: `yolo/Dockerfile.pc` + rename Jetson Dockerfile

**Files:**
- Create: `robot-ai-stack/yolo/Dockerfile.pc`
- Rename: `robot-ai-stack/yolo/Dockerfile` → `Dockerfile.jetson`

- [ ] **Step 1: Rename existing Dockerfile to Jetson variant**

Run: `git mv robot-ai-stack/yolo/Dockerfile robot-ai-stack/yolo/Dockerfile.jetson`

- [ ] **Step 2: Update `Dockerfile.jetson` CMD to run the new server**

Change the last line from `CMD ["python3", "app/detector.py"]` to:
```dockerfile
CMD ["python3", "-m", "app.yolo_server"]
```

- [ ] **Step 3: Write `Dockerfile.pc`** (x86 CUDA base, R1/R5-platform)

```dockerfile
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

RUN apt-get update && apt-get install -y \
    libxcb1 libx11-6 libxext6 libsm6 libxrender1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN PIP_INDEX_URL=https://pypi.org/simple pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY app ./app
COPY models ./models

CMD ["python3", "-m", "app.yolo_server"]
```

Note: pin `2.5.1-cuda12.4-cudnn9-runtime` — verified tag on Docker Hub compatible with RTX 3060 (Ampere, CUDA 12.x). Adjust only if a newer runtime tag is confirmed.

- [ ] **Step 4: Verify PC image builds and CUDA is visible** (partial TC-53)

Run:
```bash
cd robot-ai-stack
docker build -f yolo/Dockerfile.pc -t yolo-pc-test ./yolo
docker run --rm --gpus all yolo-pc-test python3 -c "import torch; print('cuda', torch.cuda.is_available())"
```
Expected: `cuda True`.

- [ ] **Step 5: Commit**

```bash
git add robot-ai-stack/yolo/Dockerfile.pc robot-ai-stack/yolo/Dockerfile.jetson
git commit -m "feat(yolo): x86 CUDA Dockerfile.pc; rename Jetson Dockerfile"
```

---

## Task 10: `zmq_client.py` — REQ client w/ recreate-on-timeout (TDD)

**Files:**
- Create: `.../robot_ai/robot_ai/zmq_client.py`
- Test: `.../robot_ai/test/test_zmq_client.py`

- [ ] **Step 1: Write failing tests** (TC-37, TC-39)

```python
# test/test_zmq_client.py
import threading, zmq
from robot_ai.zmq_client import ZmqReqClient

def test_timeout_returns_none_and_recovers():
    # Không có server → recv timeout → None; sau đó server lên → request OK.
    client = ZmqReqClient("tcp://127.0.0.1:5599", timeout_ms=150)
    assert client.request(b"x") is None        # TC-39 timeout -> None (socket recreated)

    ctx = zmq.Context.instance()
    rep = ctx.socket(zmq.REP)
    rep.bind("tcp://127.0.0.1:5599")
    def echo():
        msg = rep.recv(); rep.send(b"pong")
    t = threading.Thread(target=echo, daemon=True); t.start()

    assert client.request(b"ping") == b"pong"   # TC-37 recovers after prior timeout
    t.join(timeout=2); rep.close(0)
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest robot-ai-stack/ros2/workspace/src/robot_ai/test/test_zmq_client.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `zmq_client.py`**

```python
# robot_ai/zmq_client.py
import zmq

class ZmqReqClient:
    """REQ client: timeout → trả None và tái tạo socket (REQ sau timeout phải recreate)."""

    def __init__(self, endpoint: str, timeout_ms: int = 2000):
        self._endpoint = endpoint
        self._timeout = timeout_ms
        self._ctx = zmq.Context.instance()
        self._sock = None
        self._connect()

    def _connect(self) -> None:
        if self._sock is not None:
            self._sock.close(0)
        self._sock = self._ctx.socket(zmq.REQ)
        self._sock.setsockopt(zmq.RCVTIMEO, self._timeout)
        self._sock.setsockopt(zmq.LINGER, 0)
        self._sock.connect(self._endpoint)

    def request(self, data: bytes):
        """Gửi + chờ reply. None nếu timeout (đã tái tạo socket)."""
        try:
            self._sock.send(data)
            return self._sock.recv()
        except zmq.Again:
            self._connect()
            return None
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest robot-ai-stack/ros2/workspace/src/robot_ai/test/test_zmq_client.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add robot-ai-stack/ros2/workspace/src/robot_ai/robot_ai/zmq_client.py robot-ai-stack/ros2/workspace/src/robot_ai/test/test_zmq_client.py
git commit -m "feat(robot_ai): ZeroMQ REQ client with recreate-on-timeout"
```

---

## Task 11: `sample_publisher.py` node + entry point

**Files:**
- Create: `.../robot_ai/robot_ai/sample_publisher.py`
- Modify: `.../robot_ai/setup.py`, `package.xml`
- Delete: `.../robot_ai/robot_ai/image_publisher.py`

- [ ] **Step 1: Delete old publisher**

Run: `git rm robot-ai-stack/ros2/workspace/src/robot_ai/robot_ai/image_publisher.py`

- [ ] **Step 2: Implement `sample_publisher.py`** (TC-07, TC-08, TC-21, TC-22, TC-30, TC-45)

```python
# robot_ai/sample_publisher.py
import os

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node

from robot_ai_interfaces.msg import TileImage
from robot_ai.tiling import split_image

_EXTS = (".jpg", ".jpeg", ".png", ".bmp")

class SamplePublisher(Node):
    """Đọc ảnh trong folder → publish TileImage. Thay tiler bên thứ 3 khi dev."""

    def __init__(self):
        super().__init__("sample_publisher")
        self.declare_parameter("sample_dir", os.environ.get("SAMPLE_DIR", "/images"))
        self.declare_parameter("mode", "simulate_tiles")   # passthrough | simulate_tiles
        self.declare_parameter("cols", 4)
        self.declare_parameter("rows", 3)
        self.declare_parameter("period_s", 2.0)

        self._dir = self.get_parameter("sample_dir").value
        self._mode = self.get_parameter("mode").value
        self._cols = self.get_parameter("cols").value
        self._rows = self.get_parameter("rows").value
        self._bridge = CvBridge()
        self._pub = self.create_publisher(TileImage, "/image_tiles", 10)

        if not os.path.isdir(self._dir):
            self.get_logger().error(f"SAMPLE_DIR not found: {self._dir}")
            raise SystemExit(2)
        self._files = [f for f in sorted(os.listdir(self._dir)) if f.lower().endswith(_EXTS)]
        if not self._files:
            self.get_logger().warning(f"No images in {self._dir}; nothing to publish")
        self._idx = 0
        self.create_timer(self.get_parameter("period_s").value, self._tick)

    def _tick(self):
        if not self._files:
            return
        fname = self._files[self._idx % len(self._files)]
        self._idx += 1
        img = cv2.imread(os.path.join(self._dir, fname))
        if img is None:
            self.get_logger().warning(f"Unreadable image, skipping: {fname}")
            return
        h, w = img.shape[:2]
        if self._mode == "passthrough":
            self._publish_tile(fname, 0, 0, 0, 1, 0, 0, w, h, w, h, img)
        else:
            for spec, tile in split_image(img, self._cols, self._rows):
                self._publish_tile(fname, spec.index, spec.row, spec.col,
                                   self._cols * self._rows, spec.x_offset, spec.y_offset,
                                   spec.width, spec.height, w, h, tile)

    def _publish_tile(self, image_id, index, row, col, num_tiles,
                      x_off, y_off, tw, th, ow, oh, tile_img):
        msg = TileImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "sample"
        msg.image_id = image_id
        msg.tile_index = index
        msg.tile_row = row
        msg.tile_col = col
        msg.num_tiles = num_tiles
        msg.x_offset = x_off
        msg.y_offset = y_off
        msg.tile_width = tw
        msg.tile_height = th
        msg.orig_width = ow
        msg.orig_height = oh
        msg.image = self._bridge.cv2_to_imgmsg(tile_img, encoding="bgr8")
        self._pub.publish(msg)

def main():
    rclpy.init()
    try:
        node = SamplePublisher()
    except SystemExit:
        rclpy.shutdown()
        raise
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Update `setup.py` entry_points** (show full file)

```python
from setuptools import find_packages, setup

package_name = "robot_ai"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/robot_ai.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="vizo",
    maintainer_email="dev3@vizo.co.jp",
    description="Grass detection ROS2 nodes",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "sample_publisher = robot_ai.sample_publisher:main",
            "yolo_bridge = robot_ai.yolo_bridge:main",
        ],
    },
)
```

- [ ] **Step 4: Update `package.xml` deps** (add depends)

Ensure these `<depend>` entries exist:
```xml
  <depend>rclpy</depend>
  <depend>sensor_msgs</depend>
  <depend>std_msgs</depend>
  <depend>vision_msgs</depend>
  <depend>cv_bridge</depend>
  <depend>robot_ai_interfaces</depend>
```

- [ ] **Step 5: Commit**

```bash
git add robot-ai-stack/ros2/workspace/src/robot_ai/robot_ai/sample_publisher.py \
        robot-ai-stack/ros2/workspace/src/robot_ai/setup.py \
        robot-ai-stack/ros2/workspace/src/robot_ai/package.xml
git commit -m "feat(robot_ai): sample_publisher reading folder -> TileImage"
```

---

## Task 12: `yolo_bridge.py` node + Detection2DArray builder

**Files:**
- Create: `.../robot_ai/robot_ai/detection_msg.py`
- Create: `.../robot_ai/robot_ai/yolo_bridge.py`

- [ ] **Step 1: Implement `detection_msg.py`** (TC-24, TC-32, TC-49 — verified via colcon test)

```python
# robot_ai/detection_msg.py
from vision_msgs.msg import (
    BoundingBox2D, Detection2D, Detection2DArray, ObjectHypothesisWithPose,
)

def build_detection_array(header, global_dets: list[dict]) -> Detection2DArray:
    """global_dets: [{class_name, confidence, bbox:[x1,y1,x2,y2] GLOBAL}] → Detection2DArray."""
    arr = Detection2DArray()
    arr.header = header
    for d in global_dets:
        x1, y1, x2, y2 = d["bbox"]
        det = Detection2D()
        det.header = header
        bbox = BoundingBox2D()
        bbox.center.position.x = (x1 + x2) / 2.0
        bbox.center.position.y = (y1 + y2) / 2.0
        bbox.size_x = float(x2 - x1)
        bbox.size_y = float(y2 - y1)
        det.bbox = bbox
        hyp = ObjectHypothesisWithPose()
        hyp.hypothesis.class_id = str(d["class_name"])
        hyp.hypothesis.score = float(d["confidence"])
        det.results.append(hyp)
        arr.detections.append(det)
    return arr
```

- [ ] **Step 2: Implement `yolo_bridge.py`** (TC-44, integrates geometry+aggregator+zmq_client+detections)

```python
# robot_ai/yolo_bridge.py
import os

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from vision_msgs.msg import Detection2DArray
from std_msgs.msg import Header

from robot_ai_interfaces.msg import TileImage
from robot_ai.aggregator import DetectionAggregator
from robot_ai.detection_msg import build_detection_array
from robot_ai.detections import parse_detections
from robot_ai.geometry import BBox, local_to_global
from robot_ai.zmq_client import ZmqReqClient

class YoloBridge(Node):
    def __init__(self):
        super().__init__("yolo_bridge")
        port = os.environ.get("YOLO_ZMQ_PORT", "5555")
        endpoint = f"tcp://127.0.0.1:{port}"
        self._bridge = CvBridge()
        self._client = ZmqReqClient(endpoint, timeout_ms=2000)
        self._agg = DetectionAggregator(timeout_s=2.0)
        self._last_header = {}   # image_id -> Header (giữ header ảnh gốc để publish)
        self._sub = self.create_subscription(TileImage, "/image_tiles", self._on_tile, 10)
        self._pub = self.create_publisher(Detection2DArray, "/grass_detections", 10)
        self.create_timer(0.5, self._on_flush)
        self.get_logger().info(f"yolo_bridge → {endpoint}")

    def _on_tile(self, msg: TileImage):
        frame = self._bridge.imgmsg_to_cv2(msg.image, "bgr8")
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            self.get_logger().warning("imencode failed, skip tile")
            return
        reply = self._client.request(buf.tobytes())
        if reply is None:
            self.get_logger().warning("yolo_server timeout, socket recreated")
            return
        local = parse_detections(reply)
        global_dets = []
        for d in local:
            g = local_to_global(BBox(*d["bbox"]), msg.x_offset, msg.y_offset,
                                 msg.orig_width, msg.orig_height)
            global_dets.append({"class_name": d["class_name"], "confidence": d["confidence"],
                                "bbox": [g.x1, g.y1, g.x2, g.y2]})
        self._last_header[msg.image_id] = msg.header
        done = self._agg.add(msg.image_id, msg.tile_index, msg.num_tiles, global_dets)
        if done is not None:
            self._emit(msg.image_id, done)

    def _on_flush(self):
        for image_id, dets in self._agg.flush_expired():
            self._emit(image_id, dets)

    def _emit(self, image_id: str, dets: list):
        header = self._last_header.pop(image_id, Header())
        self._pub.publish(build_detection_array(header, dets))
        self.get_logger().info(f"published {len(dets)} dets for image_id={image_id}")

def main():
    rclpy.init()
    node = YoloBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit**

```bash
git add robot-ai-stack/ros2/workspace/src/robot_ai/robot_ai/detection_msg.py \
        robot-ai-stack/ros2/workspace/src/robot_ai/robot_ai/yolo_bridge.py
git commit -m "feat(robot_ai): yolo_bridge ZMQ + local->global + aggregate -> Detection2DArray"
```

---

## Task 13: Compose split + launch + ros2 Dockerfile deps

**Files:**
- Modify: `robot-ai-stack/docker-compose.yml`
- Create: `robot-ai-stack/docker-compose.pc.yml`, `docker-compose.jetson.yml`, `env.pc.example`, `env.jetson.example`
- Modify: `robot-ai-stack/ros2/Dockerfile`, `.../robot_ai/launch/robot_ai.launch.py`

- [ ] **Step 1: Rewrite `docker-compose.yml` (phần chung)**

```yaml
services:
  ros2:
    build:
      context: ./ros2
    container_name: ros2_node
    network_mode: host
    environment:
      - ROS_DOMAIN_ID=0
      - YOLO_ZMQ_PORT=5555
      - SAMPLE_DIR=/images
    volumes:
      - ./shared/images:/images
    stdin_open: true
    tty: true

  yolo:
    build:
      context: ./yolo
    container_name: yolo_detector
    network_mode: host
    environment:
      - YOLO_ZMQ_PORT=5555
      - YOLO_MODEL=/app/models/yolo26n.pt
    volumes:
      - ./shared/images:/images
      - ./models:/models
    depends_on:
      - ros2
```

- [ ] **Step 2: Write `docker-compose.pc.yml`** (TC-55)

```yaml
services:
  yolo:
    build:
      dockerfile: Dockerfile.pc
    gpus: all
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=all
```

- [ ] **Step 3: Write `docker-compose.jetson.yml`** (TC-55)

```yaml
services:
  yolo:
    build:
      dockerfile: Dockerfile.jetson
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=all
      - LD_LIBRARY_PATH=/opt/nvidia/l4t-gpu-libs/nvgpu:/usr/local/cuda/lib64
    devices:
      - nvidia.com/gpu=all
```

- [ ] **Step 4: Write env examples**

`env.pc.example`:
```
COMPOSE_FILE=docker-compose.yml:docker-compose.pc.yml
```
`env.jetson.example`:
```
COMPOSE_FILE=docker-compose.yml:docker-compose.jetson.yml
```

- [ ] **Step 5: Add deps to `ros2/Dockerfile`**

Update the apt install list to include (append after existing packages, before the `&& rm -rf`):
```dockerfile
RUN apt update && apt install -y \
    python3-pip \
    python3-opencv \
    python3-zmq \
    ros-jazzy-cv-bridge \
    ros-jazzy-image-transport \
    ros-jazzy-sensor-msgs \
    ros-jazzy-vision-msgs \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 6: Write `launch/robot_ai.launch.py`**

```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package="robot_ai", executable="sample_publisher", name="sample_publisher",
             parameters=[{"mode": "simulate_tiles", "cols": 4, "rows": 3}]),
        Node(package="robot_ai", executable="yolo_bridge", name="yolo_bridge"),
    ])
```

- [ ] **Step 7: Validate compose config resolves per platform** (TC-55)

Run:
```bash
cd robot-ai-stack
docker compose -f docker-compose.yml -f docker-compose.pc.yml config | grep -E "dockerfile|gpus|LD_LIBRARY_PATH" || true
```
Expected: shows `dockerfile: Dockerfile.pc`, `gpus`, and NO `LD_LIBRARY_PATH`. Repeat with `docker-compose.jetson.yml` → shows `Dockerfile.jetson`, `devices`, and the L4T `LD_LIBRARY_PATH`.

- [ ] **Step 8: Commit**

```bash
git add robot-ai-stack/docker-compose.yml robot-ai-stack/docker-compose.pc.yml \
        robot-ai-stack/docker-compose.jetson.yml robot-ai-stack/env.pc.example \
        robot-ai-stack/env.jetson.example robot-ai-stack/ros2/Dockerfile \
        robot-ai-stack/ros2/workspace/src/robot_ai/launch/robot_ai.launch.py
git commit -m "feat(compose): platform override files + launch + ros2 deps"
```

---

## Task 14: Build, run, E2E verify on PC

**Files:** none (verification)

- [ ] **Step 1: Run pure-logic tests (host)**

Run: `cd robot-ai-stack/ros2/workspace/src/robot_ai && python3 -m pytest test/ -v && cd ../../../../yolo && python3 -m pytest tests/ -v`
Expected: all green (Tasks 3–8, 10 tests).

- [ ] **Step 2: colcon build + colcon test (ROS2)** (TC-47, TC-32, TC-49)

Run:
```bash
cd robot-ai-stack/ros2/workspace
colcon build
source install/setup.bash
colcon test --packages-select robot_ai robot_ai_interfaces
colcon test-result --verbose
```
Expected: build OK, tests pass.

- [ ] **Step 3: Bring up the stack on PC**

Run:
```bash
cd robot-ai-stack
cp env.pc.example .env
# đảm bảo shared/images có 1 ảnh 4K test (đổi tên test.jpg thành ảnh 3840x2160 nếu cần)
docker compose up --build -d
docker compose logs yolo | grep "device="
```
Expected: `[yolo_server] device=cuda ...` and `listening on tcp://*:5555`.

- [ ] **Step 4: E2E — assert Detection2DArray** (TC-54)

Run (in the ros2 container or host with ROS2 sourced):
```bash
docker compose exec ros2 bash -lc "source /opt/ros/jazzy/setup.bash && source /workspace/install/setup.bash && \
  ros2 launch robot_ai robot_ai.launch.py &   sleep 8; \
  ros2 topic echo --once /grass_detections"
```
Expected: a `Detection2DArray` message prints; every `bbox.center` within `[0..3840]×[0..2160]`. (With COCO model the classes are COCO, not grass — luồng đúng là mục tiêu; weights cỏ thay sau.)

- [ ] **Step 5: Error-path smoke** (TC-39)

Run:
```bash
docker compose stop yolo
docker compose logs -f ros2 | grep -m1 "timeout"   # bridge logs timeout, không crash
docker compose start yolo
```
Expected: bridge logs "yolo_server timeout", recovers after restart.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "test: E2E verification notes for PC stack"
```

---

## Self-Review

**Spec coverage:** R1 (Task 9,13), R2 (Task 7,8), R3 (Task 5,7,8,12), R4 (Task 3,12), R5 (Task 3), R6 (Task 6,12), R7 (Task 12), R8 (Task 2,11), R9 (Task 11), R10 (Task 5,8,10,12), R11 (Task 7,8), R12 (Task 2). All requirements have tasks.

**Placeholder scan:** No TBD/TODO; all code steps contain full code; commands have expected output.

**Type consistency:** `BBox(x1,y1,x2,y2)` used consistently (Task 3, 12). Detection dict schema `{class_id,class_name,confidence,bbox}` consistent across `detections.py`, `inference.py`, `yolo_bridge.py`; `build_detection_array` consumes `{class_name,confidence,bbox}`. `DetectionAggregator.add(image_id,tile_index,num_tiles,dets)` / `flush_expired()` used identically in tests and `yolo_bridge`. `ZmqReqClient.request()` returns bytes|None as used in bridge. `TileImage` fields match msg definition and `sample_publisher` setters.

**Known follow-ups (out of MVP scope):** grass weights; overlap+NMS; throughput/parallel REQ; ONNX/TensorRT; Jetson build/verify (Phase 5).
