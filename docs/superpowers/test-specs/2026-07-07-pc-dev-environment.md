# Test Spec — Bản chạy PC + pipeline tiling/toạ độ + tách YOLO khỏi ROS2

Source design spec: docs/superpowers/specs/2026-07-07-pc-dev-environment-design.md
Date: 2026-07-07

## Requirements (rút từ design spec)
- **R1** (§3,§5): Tách nền tảng qua compose override + `.env`/`COMPOSE_FILE` chọn PC vs Jetson.
- **R2** (§3): `yolo_server` KHÔNG phụ thuộc ROS2; giao tiếp qua ZeroMQ REP.
- **R3** (§4.2): Giao thức ZeroMQ — request = JPEG, reply = JSON detections toạ độ LOCAL.
- **R4** (§3): Transform LOCAL→GLOBAL: `gx = x_offset + lx`, `gy = y_offset + ly`.
- **R5** (§7): Clamp toạ độ global về `[0..orig_w]×[0..orig_h]`.
- **R6** (§3,§7): Aggregate theo `image_id` đến khi đủ `num_tiles` **hoặc** hết `AGG_TIMEOUT`.
- **R7** (§4.3): Đầu ra `vision_msgs/Detection2DArray` (center/size px + class_id + score).
- **R8** (§4.1): Contract `TileImage` mang metadata offset/index/orig.
- **R9** (§6): `sample_publisher` đọc `SAMPLE_DIR`; 2 chế độ `passthrough` + `simulate_tiles` (4×3).
- **R10** (§7): Xử lý lỗi — ZMQ timeout recreate socket; ảnh hỏng → `[]`; model/GPU fail → exit non-zero.
- **R11** (§3): Lọc class mục tiêu qua `YOLO_TARGET_CLASSES` (tuỳ chọn).
- **R12** (§6): Package `robot_ai_interfaces` build được (rosidl), `TileImage` import được ở 2 node.

> Ghi chú hermetic: các case transform/aggregate/tiling dùng **detections giả (mock)** cố định, KHÔNG chạy model thật, để deterministic. Model thật chỉ xuất hiện ở E2E/critical path với tolerance.

## Coverage summary
- Invalid inputs: 9 cases
- Boundary values: 9 cases
- Null / empty / missing: 6 cases
- Equivalence classes: 8 cases
- State / ordering / idempotency: 6 cases
- Error paths: 5 cases
- Side effects / observability: 6 cases
- Determinism / reproducibility: 2 cases
- Regression / parity: 2 cases
- Critical path: 2 cases
- Happy path: 2 cases
- Security / untrusted input: N/A — chỉ đọc folder do operator cấu hình; không có input mạng/untrusted trong MVP.
- Concurrency / races: N/A — single executor thread + REQ/REP lockstep; không có nhiều writer trong MVP.
- Resource / performance bounds: N/A — spec không đặt ngưỡng hiệu năng cho MVP (throughput ngoài phạm vi); giới hạn bộ nhớ buffer aggregate được phủ bởi TC-40.
- Recovery / resumability: phủ bởi TC-35, TC-37 (khôi phục socket sau timeout).

## Cases

### Invalid inputs
- **TC-01** — transform: bbox đảo ngược `x2<x1` (vd `[50,20,10,60]`) → chuẩn hoá về `min/max` trước khi cộng offset, size không âm — *reason:* model có thể trả bbox lệch thứ tự, không được sinh size âm — *covers:* R4,R7
- **TC-02** — transform: bbox có toạ độ âm (`lx1=-5`) → sau offset, clamp về `0` — *reason:* không cho toạ độ global âm — *covers:* R5
- **TC-03** — yolo_server: nhận bytes không phải JPEG hợp lệ → reply `[]`, log, không crash — *reason:* dữ liệu hỏng không được làm chết server — *covers:* R3,R10
- **TC-04** — yolo_server: nhận bytes rỗng (0 byte) → reply `[]`, không crash — *reason:* frame rỗng phải an toàn — *covers:* R10
- **TC-05** — bridge/aggregate: `TileImage.num_tiles=0` → bỏ qua, log cảnh báo, không publish — *reason:* metadata vô lý không được kích hoạt aggregate — *covers:* R6,R8
- **TC-06** — aggregate: 1 detection thiếu field bắt buộc (`bbox` không có) → bỏ detection đó, log, không crash — *reason:* reply lỗi một phần không được làm hỏng cả frame — *covers:* R3,R10
- **TC-07** — sample_publisher: `SAMPLE_DIR` có file không phải ảnh (`.txt`) → bỏ qua, tiếp tục — *reason:* folder lẫn file lạ là bình thường — *covers:* R9
- **TC-08** — sample_publisher: file ảnh hỏng/không đọc được → bỏ qua + log, vẫn publish các ảnh còn lại — *reason:* 1 ảnh hỏng không chặn cả batch — *covers:* R9
- **TC-09** — config: `YOLO_ZMQ_PORT` không phải số → lỗi khởi động rõ ràng (cả server & bridge) — *reason:* cấu hình sai phải fail-fast, không bind port rác — *covers:* R2,R3

### Boundary values
- **TC-10** — transform: bbox đúng mép tile (`lx2 = tile_width`) → global = `x_offset + tile_width`; nếu bằng `orig_width` thì giữ nguyên (không clamp thừa) — *reason:* biên tile là off-by-one phổ biến — *covers:* R4,R5
- **TC-11** — transform: sau offset vượt `orig_width` đúng 1px → clamp về `orig_width` — *reason:* just-outside phải bị kẹp — *covers:* R5
- **TC-12** — transform: tile góc cuối (`x_offset=orig_w-tile_w`, `y_offset=orig_h-tile_h`) bbox ở góc xa → map tới `(orig_w, orig_h)` — *reason:* tile cực biên — *covers:* R4,R5
- **TC-13** — transform: `tile_index=0` (offset 0,0) và `tile_index=num_tiles-1` đều map đúng — *reason:* phần tử đầu/cuối — *covers:* R4
- **TC-14** — aggregate: nhận đúng `num_tiles=12` → emit đúng 1 lần, buffer được xoá — *reason:* đủ số tile là điều kiện emit chính — *covers:* R6
- **TC-15** — aggregate: 11/12 tile rồi hết `AGG_TIMEOUT` → flush phần dở (11 tile) — *reason:* thiếu tile không được treo vô hạn — *covers:* R6,R10
- **TC-16** — aggregate: `num_tiles=1` (passthrough) → emit ngay sau 1 tile — *reason:* biên nhỏ nhất — *covers:* R6,R9
- **TC-17** — tiling: split đúng `3840×2160` theo `4×3` → 12 tile mỗi tile `960×720`, offset cuối `(2880,1440)` — *reason:* cấu hình chuẩn phải chính xác từng pixel — *covers:* R9
- **TC-18** — tiling: kích thước không chia hết grid (vd `3841×2161`) → tile cuối gánh phần dư (`961/721`), phủ hết ảnh không hở/không chồng — *reason:* off-by-one khi không chia hết — *covers:* R9

### Null / empty / missing
- **TC-19** — aggregate: 1 tile trả detections rỗng `[]` vẫn được tính vào `num_tiles` — *reason:* tile không có cỏ vẫn là tile hợp lệ — *covers:* R6
- **TC-20** — aggregate: cả 12 tile trả `[]` → emit `Detection2DArray` với `detections=[]` (header vẫn set) — *reason:* ảnh không có cỏ vẫn phải phát 1 msg hợp lệ — *covers:* R6,R7
- **TC-21** — sample_publisher: `SAMPLE_DIR` rỗng → node khởi động, log cảnh báo, không publish, không crash — *reason:* folder rỗng là trạng thái hợp lệ — *covers:* R9
- **TC-22** — sample_publisher: `SAMPLE_DIR` không tồn tại → lỗi rõ ràng khi khởi động — *reason:* path sai phải fail-fast — *covers:* R9
- **TC-23** — TileImage: `frame_id` rỗng/absent → aggregate vẫn khoá theo `image_id` (không phụ thuộc frame_id) — *reason:* field optional không được làm hỏng gom — *covers:* R8
- **TC-24** — bridge: `Detection2DArray.header` (stamp + frame_id) được set kể cả khi `detections` rỗng — *reason:* downstream cần header hợp lệ luôn — *covers:* R7

### Equivalence classes of valid input
- **TC-25** — transform: bbox trong tile nội (offset >0 cả 2 trục) → global đúng — *reason:* lớp tile "giữa" — *covers:* R4
- **TC-26** — transform: tile hàng trên (`y_offset=0`) vs cột trái (`x_offset=0`) vs nội → mỗi lớp đúng — *reason:* các lớp biên khác nhau — *covers:* R4
- **TC-27** — yolo_server: ảnh có nhiều detection (>1) → JSON list đúng số lượng — *reason:* lớp "nhiều vật" — *covers:* R3
- **TC-28** — yolo_server: ảnh có đúng 1 detection → list dài 1 — *reason:* lớp "một vật" — *covers:* R3
- **TC-29** — model: nạp `.pt` (COCO) thành công; ghi chú `.onnx`/`.engine` dùng chung interface ultralytics (future) — *reason:* xác nhận backend `.pt` — *covers:* R2
- **TC-30** — sample_publisher: folder có `.jpg` và `.png` → publish cả hai — *reason:* lớp định dạng ảnh — *covers:* R9
- **TC-31** — filter: `YOLO_TARGET_CLASSES` set (vd "grass") → chỉ trả class mục tiêu; unset → trả tất cả — *reason:* 2 lớp cấu hình lọc — *covers:* R11
- **TC-32** — bridge→output: mỗi detection → `Detection2D` với `results[0].hypothesis.class_id`=tên class, `score`=confidence, `bbox.center/size` px — *reason:* lớp ánh xạ trường chuẩn vision_msgs — *covers:* R7

### State / ordering / idempotency
- **TC-33** — aggregate: tile tới sai thứ tự (index 5 trước 0) → vẫn gom đúng theo `image_id`, độc lập thứ tự — *reason:* mạng/định thời không đảm bảo thứ tự — *covers:* R6
- **TC-34** — aggregate: trùng `tile_index` cùng `image_id` (tile 3 hai lần) → dedup, không vượt `num_tiles`, không emit sớm sai — *reason:* gửi lại/nhân đôi phải an toàn — *covers:* R6,R10
- **TC-35** — aggregate: `image_id=B` tới khi `A` chưa đủ → 2 buffer độc lập, không lẫn — *reason:* nhiều ảnh gối nhau — *covers:* R6
- **TC-36** — aggregate: `A` đã emit & xoá; tile trễ của `A` tới sau → không tái emit "ma" — *reason:* idempotency sau hoàn tất — *covers:* R6,R10
- **TC-37** — bridge: REQ sau một lần timeout → socket được tái tạo, request kế thành công — *reason:* trạng thái REQ phải khôi phục — *covers:* R10
- **TC-38** — transform: hàm thuần — cùng input cho cùng output qua nhiều lần gọi, không state ẩn — *reason:* idempotent/pure — *covers:* R4

### Error paths
- **TC-39** — bridge: `yolo_server` không phản hồi trong `RCVTIMEO` → log timeout, recreate REQ socket, bỏ detections của tile đó, tiếp tục spin (không deadlock) — *reason:* server treo không được làm chết bridge — *covers:* R10
- **TC-40** — yolo_server: path model sai/không tồn tại lúc khởi động → exit non-zero, log rõ — *reason:* thiếu model phải fail-fast — *covers:* R10
- **TC-41** — yolo_server: `torch.cuda.is_available()==False` → log cảnh báo + thiết bị, fallback CPU vẫn chạy — *reason:* thiếu GPU không nên chặn dev; phải quan sát được — *covers:* R10
- **TC-42** — aggregate: `AGG_TIMEOUT` hết với `image_id` đăng ký nhưng 0 tile giao → buffer được dọn, không rò rỉ bộ nhớ — *reason:* chặn buffer phình vô hạn — *covers:* R6,R10
- **TC-43** — bridge: reply JSON sai định dạng từ server → log, bỏ qua, tiếp tục (không crash) — *reason:* reply hỏng phải chịu lỗi mềm — *covers:* R3,R10

### Side effects / observability
- **TC-44** — bridge: publish `/grass_detections` **đúng 1 lần** mỗi `image_id` hoàn tất — *reason:* không phát trùng/thiếu — *covers:* R6,R7
- **TC-45** — sample_publisher: publish N msg cho N ảnh (passthrough) / `12×N` (simulate_tiles) — *reason:* số lượng phát đúng theo chế độ — *covers:* R9
- **TC-46** — yolo_server: log thiết bị (CUDA/CPU) lúc khởi động — *reason:* quan sát được nơi inference chạy — *covers:* R10
- **TC-47** — interfaces: `robot_ai_interfaces` build (colcon) và `TileImage` import được ở cả 2 node — *reason:* contract phải build & dùng được — *covers:* R12,R8
- **TC-48** — yolo_server: import module KHÔNG cần `rclpy`/`cv_bridge` (giả lập môi trường thiếu ROS2 vẫn import OK) — *reason:* đảm bảo YOLO tách rời ROS2 thật sự — *covers:* R2
- **TC-49** — bridge: mỗi `Detection2D.bbox` có `center`,`size_x`,`size_y` > 0 với detection hợp lệ — *reason:* bbox hợp lệ cho downstream — *covers:* R7

### Determinism / reproducibility
- **TC-50** — transform+aggregate: cùng tập tile+detections (mock) → `Detection2DArray` giống hệt, thứ tự detections ổn định — *reason:* kết quả tái lập được — *covers:* R4,R6
- **TC-51** — tiling: split deterministic — cùng ảnh → cùng tile/offset mỗi lần — *reason:* không phụ thuộc trạng thái máy — *covers:* R9

### Regression / parity
- **TC-52** — parity output: detection mang tên class + confidence tương đương ngữ nghĩa `detector.py` cũ (`class`,`confidence`), bổ sung `bbox` — *reason:* không mất thông tin so với bản cũ — *covers:* R7
- **TC-53** — parity nền tảng: cùng input tile + cùng model → PC và Jetson cho detection/toạ độ tương đương (tolerance float) — *reason:* 2 nền tảng phải đồng nhất hành vi — *covers:* R1

### Critical path
- **TC-54** — E2E: `sample_publisher(simulate_tiles)` đẩy ảnh 4K test → 12 `TileImage` → `yolo_bridge` → `yolo_server` → đúng 1 `Detection2DArray` trên `/grass_detections`, mọi bbox nằm trong `[0..3840]×[0..2160]` — *reason:* luồng đầu-cuối chính — *covers:* R1,R3,R4,R5,R6,R7
- **TC-55** — config: `docker compose -f docker-compose.yml -f docker-compose.pc.yml config` cho ra `Dockerfile.pc` + `gpus:all` + KHÔNG `LD_LIBRARY_PATH` L4T; biến thể jetson cho `Dockerfile.jetson` + `devices` + L4T path — *reason:* override chọn đúng cấu hình mỗi nền tảng — *covers:* R1

### Happy path (last)
- **TC-56** — transform: bbox `[10,20,50,60]` trong tile offset `(960,720)` → global `[970,740,1010,780]` — *reason:* trường hợp đúng đơn giản nhất — *covers:* R4
- **TC-57** — passthrough: 1 ảnh → 1 `TileImage(num_tiles=1)` → 1 `Detection2DArray` — *reason:* luồng tối giản chạy được — *covers:* R6,R9

## Traceability
| Requirement | Case ids |
|---|---|
| R1 tách nền tảng | TC-53, TC-54, TC-55 |
| R2 YOLO không ROS2 / ZMQ REP | TC-09, TC-29, TC-48 |
| R3 giao thức ZMQ | TC-03, TC-04, TC-06, TC-27, TC-28, TC-43, TC-54 |
| R4 transform LOCAL→GLOBAL | TC-01, TC-10, TC-12, TC-13, TC-25, TC-26, TC-38, TC-50, TC-54, TC-56 |
| R5 clamp | TC-02, TC-10, TC-11, TC-12 |
| R6 aggregate | TC-05, TC-14, TC-15, TC-16, TC-19, TC-20, TC-33, TC-34, TC-35, TC-36, TC-42, TC-44, TC-50, TC-54, TC-57 |
| R7 Detection2DArray | TC-20, TC-24, TC-32, TC-44, TC-49, TC-52, TC-54 |
| R8 TileImage contract | TC-05, TC-23, TC-47 |
| R9 sample_publisher | TC-07, TC-08, TC-16, TC-17, TC-18, TC-21, TC-22, TC-30, TC-45, TC-51, TC-57 |
| R10 xử lý lỗi | TC-03, TC-04, TC-06, TC-34, TC-36, TC-37, TC-39, TC-40, TC-41, TC-42, TC-43, TC-46 |
| R11 lọc class | TC-31 |
| R12 interfaces build | TC-47 |
