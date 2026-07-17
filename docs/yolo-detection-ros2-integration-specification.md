# YOLO Detection ROS 2連携仕様書（プロトタイプ版）

## 改訂履歴

| 日付 | 文書バージョン | 内容 |
| --- | --- | --- |
| 2026-07-17 | 1.1.0 | YOLO Detection への名称統一、出力 topic・message・配列 field を更新 |
| 2026-07-13 | 1.0.0 | v1.0.0 ドラフト |

## 目次

1. [接続の必須条件](#connection)
2. [処理フローとスループット上の制約](#flow)
3. [入力仕様](#input)
4. [出力仕様](#output)
5. [連携時の注意事項](#checklist)

## 用語集

| 用語 | 説明 |
| --- | --- |
| Message / <code>.msg</code> | ROS 2 で事前定義されたデータ構造です。双方が同一の <code>robot_ai_interfaces</code> 定義を使用する必要があります。 |
| Type hash | ROS 2 が message 構造の一致を確認するための識別子です。<code>.msg</code> が異なると publisher と subscriber が接続できないことがあります。 |
| <code>ROS_DOMAIN_ID</code> | ROS 2 の通信領域を表す番号です。同じ domain の node だけが相互に検出できます。システムの既定値は <code>0</code> です。 |
| Discovery | ROS 2 が同じ domain 内の node と topic を自動検出する仕組みです。<code>LOCALHOST</code> は検出範囲を同一ホストに限定します。 |
| QoS | message 配信のルールです。信頼性、保持する message 数、過去 message の再配信有無などを定めます。 |
| <code>reliable</code> / <code>volatile</code> | <code>reliable</code> は middleware が信頼性を持って配信しようとする設定です。<code>volatile</code> では、あとから接続した subscriber に過去の結果は再送されません。 |
| Tile | 元画像から切り出した小さな画像領域です。1 枚の元画像は複数の tile として処理されます。 |
| ZeroMQ REQ/REP | システム内部の通信方式です。bridge が tile を要求（REQ）として送り、<code>yolo_server</code> から応答（REP）を待ちます。 |
| Aggregator | 同一 <code>image_id</code> の各 tile に対する detection を集約し、元画像単位の結果を出力するコンポーネントです。 |
| LOCAL / GLOBAL | LOCAL は tile 内の座標、GLOBAL は元画像全体の座標です。bridge は <code>x_offset</code> と <code>y_offset</code> を加算して LOCAL を GLOBAL に変換します。 |
| Instance segmentation | 画像内の物体をインスタンス単位で識別し、各インスタンスの class と輪郭を出力する方式です。 |
| Polygon | 物体の輪郭を表す点列です。segmentation model が返す場合があります。bbox のみの model では空になります。 |
| Clamp | bbox または polygon の座標が元画像の範囲外に出ないよう、画像境界内に制限する処理です。 |
| NMS / dedup | 重複する detection を取り除く技術です。現行システムでは tile 間には適用されないため、overlap があると重複結果が出る可能性があります。 |

---

<a id="connection"></a>

## 1. 接続の必須条件

| 項目 | 内容 |
| --- | --- |
| ROS | ROS 2 **Jazzy** |
| Python | ホスト上で native node を実行する場合は **3.12**。container 実行時はシステム image に含まれる Python を使用します。 |
| Docker | Docker Engine **29.x**（現行検証環境: **29.1.5**） |
| Message package | システムと**同一 revision/tag** の <code>robot_ai_interfaces</code> を build・source してください。<code>.msg</code> をコピーして改変してはいけません。type hash が一致する必要があります。 |
| <code>ROS_DOMAIN_ID</code> | 両側で同じ値にしてください。システムの既定値は <code>0</code> です。 |
| 同一ホスト discovery | システムは <code>ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST</code> を使用します。パートナー node は同一 host/loopback 上で実行してください。host 上の native 実行、または <code>network_mode: host</code> の container が利用できます。パートナー側にも同じ環境変数を設定し、discovery を loopback に限定してください。独立した bridge network の container からは検出できません。 |
| 画像 encoding | <code>sensor_msgs/Image.encoding = bgr8</code> |
| Trust boundary | 現行 contract の ROS 2 topic には認証がありません。同一 host・同一 domain 内では、信頼できる process/container のみを実行してください。 |

package を build した後、パートナー workspace を source してから node を起動してください。discovery と type は次のコマンドで確認できます。

~~~bash
ros2 topic info /image_tiles -v
ros2 topic info /detected_instances -v
~~~

両 topic の既定 QoS は **reliable、keep-last depth 10、volatile** です。結果が publish される前に subscriber を起動してください。late-joiner に過去の結果は再配信されません。

---

<a id="flow"></a>

## 2. 処理フローとスループット上の制約

~~~mermaid
flowchart LR
  subgraph Partner["パートナー（同一ホスト上の ROS 2）"]
    TILER["Tiler<br/>元画像 → N tile"]
    DS["Downstream<br/>（結果受信側）"]
  end
  subgraph System["YOLO Detection システム"]
    BR["yolo_bridge"]
    YS["yolo_server<br/>（YOLO inference・GPU）"]
  end

  TILER -->|"/image_tiles · TileImage<br/>（1 画像あたり N message）"| BR
  BR <-->|"ZeroMQ REQ/REP<br/>（システム内部）"| YS
  BR -->|"/detected_instances · DetectedInstanceArray<br/>（1 画像あたり最大 1 message）"| DS
~~~

- tiler は <code>/image_tiles</code> に publish し、downstream は <code>/detected_instances</code> を subscribe します。
- tile の到着順は任意です。bridge は <code>image_id</code> と <code>tile_index</code> で集約します。
- YOLO は ZeroMQ REQ/REP を通じて tile を逐次処理します。1 画像の処理時間は各 tile の inference 時間の合計におおむね比例します。FPS と同時処理する frame 数は、実機 GPU 上で benchmark して決定してください。
- tile 間の global NMS/dedup は実行しません。overlap を使用する場合、同一物体が <code>instances[]</code> に複数回現れることがあります。overlap を使わない、overlap 領域の担当を決める、または downstream で dedup する方針を事前に決めてください。

---

<a id="input"></a>

## 3. 入力仕様（<code>/image_tiles</code>）

~~~mermaid
sequenceDiagram
    participant P as Tiler（パートナー）
    participant B as yolo_bridge（システム）
    Note over P: 1 元画像 → N tile<br/>一意な image_id を生成
    loop 各 tile i = 0 .. N-1（順序は任意）
        P->>B: /image_tiles: TileImage
    end
    Note over B: 各 tile を inference し、image_id ごとに集約
~~~

- **Topic:** <code>/image_tiles</code>
- **Type:** <code>robot_ai_interfaces/msg/TileImage</code>
- **QoS:** reliable、keep-last depth 10、volatile

### 3.1. TileImage の定義

~~~
std_msgs/Header header
string   image_id
uint16   tile_index
uint16   tile_row
uint16   tile_col
uint16   num_tiles
uint32   x_offset
uint32   y_offset
uint32   tile_width
uint32   tile_height
uint32   orig_width
uint32   orig_height
sensor_msgs/Image image
~~~

| Field | 意味 | 必須の制約 |
| --- | --- | --- |
| <code>header.stamp</code> | 撮影時刻 | 同じ <code>image_id</code> の全 tile で同じ stamp を使用します。 |
| <code>header.frame_id</code> | 送信元 frame（任意） | 空でも構いません。output では trace 用に <code>image_id</code> を使用します。 |
| <code>image_id</code> | 元画像の一意な ID | <code>source/timestamp/sequence</code> 形式を使用し、再利用しないでください。 |
| <code>tile_index</code> | tile の番号 | <code>0..num_tiles-1</code> の各値を 1 回ずつ使用してください。 |
| <code>tile_row</code>、<code>tile_col</code> | grid 上の位置 | trace/debug 用です。bridge は集約に使用しません。 |
| <code>num_tiles</code> | tile の総数 | <code>> 0</code>。同じ画像のすべての tile で同一値にしてください。 |
| <code>x_offset</code>、<code>y_offset</code> | 元画像内における tile 左上の座標 | pixel 単位で正確に設定してください。 |
| <code>tile_width</code>、<code>tile_height</code> | tile のサイズ | <code>image</code> の実際のサイズと一致させてください。 |
| <code>orig_width</code>、<code>orig_height</code> | 元画像のサイズ | <code>> 0</code>。同じ画像の全 tile で同一値にしてください。output 座標の clamp に使用されます。 |
| <code>image</code> | tile の pixel データ | <code>bgr8</code> で、有効な画像データである必要があります。 |

### 3.2. 入力時の規約

- 同じ画像の tile は任意の順序で到着できますが、index の欠落、余分な index、重複があってはいけません。
- tile 間で metadata が不整合、index が範囲外、画像が空、encode/inference が失敗した場合、現行 contract での結果は**未定義**です。publisher 側で publish 前に防止してください。
- 重複 tile は結果集約時に破棄されることがあります。retry の仕組みとして利用しないでください。
- 完了済みの <code>image_id</code> は bridge 内のサイズ制限付き cache にだけ保持されます。同じ ID を再送すれば必ず破棄される、とは想定しないでください。

**例** — <code>3840×2160</code> の元画像を <code>4×3 = 12</code> tile に分割した場合の最後の tile:

~~~
image_id="camera-a/2026-07-13T09:20:15.123Z/7f3e",
tile_index=11, tile_row=2, tile_col=3, num_tiles=12,
x_offset=2880, y_offset=1440, tile_width=960, tile_height=720,
orig_width=3840, orig_height=2160, image=<bgr8 960x720>
~~~

---

<a id="output"></a>

## 4. 出力仕様（<code>/detected_instances</code>）

~~~mermaid
sequenceDiagram
    participant B as yolo_bridge（システム）
    participant D as Downstream（パートナー）
    Note over B: LOCAL（tile）→ GLOBAL（元画像）、clamp
    B->>D: /detected_instances: DetectedInstanceArray
    Note over D: image_id で元画像に対応付け
~~~

- **Topic:** <code>/detected_instances</code>
- **Type:** <code>robot_ai_interfaces/msg/DetectedInstanceArray</code>
- **QoS:** reliable、keep-last depth 10、volatile

### 4.1. 出力発行条件

bridge は次のいずれかで output を作成します。

1. **Complete:** inference が成功した tile を <code>num_tiles</code> 個すべて受信し、各 <code>tile_index</code> が一意である場合。
2. **Timeout による partial:** 少なくとも 1 tile の inference は成功したものの、すべて揃う前に aggregation timeout（現在 **2 秒**）に達した場合。timer は 0.5 秒ごとに確認するため、厳密な real-time SLA ではありません。

tile を encode できない、または YOLO timeout となった場合、その tile は aggregator に入りません。ある <code>image_id</code> について**1 tile も** inference に成功しなかった場合、flush 対象の buffer が作られないため、output は発行されません。

現行 schema には <code>status</code>、<code>received_tiles</code>、<code>expected_tiles</code> がありません。そのため downstream は、complete、partial、または detection がないための <code>instances=[]</code> を区別できません。運用上、すべての tile が処理されたことを保証できる場合にのみ、<code>instances=[]</code> を「検出なし」と判断してください。安全性が必要な production 判断では、status metadata を contract に追加する必要があります。

### 4.2. 出力メッセージの構造

~~~
# DetectedInstanceArray.msg
std_msgs/Header header        # frame_id = image_id
string         image_id
DetectedInstance[] instances

# DetectedInstance.msg
string                class_name
float32               score
BBox2D                bbox
geometry_msgs/Polygon polygon

# BBox2D.msg
float32 center_x
float32 center_y
float32 size_x
float32 size_y
~~~

| Field | 意味と規約 |
| --- | --- |
| <code>header.frame_id</code> | bridge が trace 用に <code>image_id</code> を設定します。 |
| <code>header.stamp</code> | input の元画像の stamp です。 |
| <code>image_id</code> | 送信済み ID と一致し、結果の対応付けに使用します。 |
| <code>instances[].class_name</code> | production weights に定義された class 名です。出力値は、導入済み model の class 一覧に限定されます。 |
| <code>instances[].score</code> | confidence。範囲は <code>[0..1]</code> です。 |
| <code>instances[].bbox</code> | 元画像上の GLOBAL bbox。center + size 形式、pixel 単位です。 |
| <code>instances[].polygon.points[]</code> | model が segmentation を返す場合の GLOBAL polygon です。detection-only の場合は空です。各 point は元画像上の pixel 座標 <code>x</code>、<code>y</code> を使用します。 |

**座標規約:** 原点 <code>(0,0)</code> は左上です。bridge は bbox/polygon を連続的な画像境界 <code>[0..orig_width] × [0..orig_height]</code> に clamp します。そのため右端・下端は <code>orig_width</code>/<code>orig_height</code> と同じ値になり得ます。これは最後の pixel 中心の index（<code>width - 1</code>/<code>height - 1</code>）とは異なります。

**center/size から角座標への変換:**

~~~
x1 = center_x - size_x / 2
y1 = center_y - size_y / 2
x2 = center_x + size_x / 2
y2 = center_y + size_y / 2
~~~

<code>instances[]</code> の順序は API の保証ではありません。配列内の位置を識別子として使用しないでください。

**output 例**（JSON による表現）:

~~~json
{
  "image_id": "camera-a/2026-07-13T09:20:15.123Z/7f3e",
  "header": {
    "frame_id": "camera-a/2026-07-13T09:20:15.123Z/7f3e",
    "stamp": { "sec": 1783934415, "nanosec": 123000000 }
  },
  "instances": [
    {
      "class_name": "target_class",
      "score": 0.91,
      "bbox": {
        "center_x": 848.5,
        "center_y": 1292.6,
        "size_x": 79.7,
        "size_y": 269.5
      },
      "polygon": {
        "points": [
          { "x": 810, "y": 1157 },
          { "x": 888, "y": 1157 },
          { "x": 888, "y": 1427 },
          { "x": 810, "y": 1427 }
        ]
      }
    }
  ]
}
~~~

上記の <code>target_class</code> は message 形式を示す例です。実際の値は production weights に定義された class 名を使用します。

### 4.3. 認識対象とクラス定義

<code>instances[]</code> の各要素は、画像内で認識された 1 つの対象インスタンスを表します。各対象インスタンスには <code>class_name</code>、画像軸に平行な bbox、および segmentation model が利用可能な場合は polygon が含まれます。bbox は回転角を持ちません。

認識対象および <code>class_name</code> は production weights によって定義されます。本仕様では、特定の物体または class に限定しません。

| 項目 | 定義 |
| --- | --- |
| 認識対象 | production weights に定義された detection または segmentation の対象です。 |
| <code>class_name</code> | model が返す class 名です。出力値は production weights の class 一覧に限定されます。 |

bridge は model の class 名を変換せずに出力します。導入前に、使用する class 名と認識対象の範囲を双方で合意してください。

---

<a id="checklist"></a>

## 5. 連携時の注意事項

同一画像の全 tile に対して、同じ ROS 2 domain、message package および正しい metadata を使用してください。input を publish する前に `/detected_instances` を subscribe し、結果は `image_id` で対応付けます。

結果を受信できない場合は、`ros2 topic info -v` と `yolo_bridge` の log を確認してください。すべての tile が timeout/error となった場合、現行システムはその画像の output を発行しません。

導入前に、weights/class、FPS、tile overlap、および partial result の取り扱いを合意してください。
