# veriq — 要求検証ツール

> [!WARNING]
> このパッケージは現在活発に開発中です。
> 既知の問題と制限があります。

`veriq`は、エンジニアリングプロジェクト全体の要求、計算、検証を管理するのに役立ちます。計算間の依存関係を追跡し、要求が満たされているかを自動的に検証するスマートなスプレッドシートと考えてください。

## クイックスタート

veriqをインストール：

```bash
pip install veriq
```

## veriqを理解する：スプレッドシートの類似性

Excelなどのスプレッドシートを使ったことがあれば、veriqの基本概念は既に理解しています：

### スプレッドシート → veriq の概念

| スプレッドシート       | veriq            | 説明                                                          |
| ---------------------- | ---------------- | ------------------------------------------------------------- |
| **ワークブック**       | **Project**      | すべてを含む最上位のコンテナ                                  |
| **シート**             | **Scope**        | 論理的なグループ（例：「Power」、「Thermal」、「Structure」） |
| **入力セル**           | **Model**        | 提供する設計パラメータ（バッテリー容量など）                  |
| **数式セル**           | **Calculation**  | 計算された値（`=B2*0.3`のような）                             |
| **条件付き書式ルール** | **Verification** | 値が要求を満たすかをチェック（`<=85`のような）                |

スプレッドシートと同様に：

- 設計パラメータ（モデルデータ）を入力する
- veriqが派生値を自動的に計算する
- 要求が満たされているかをチェックする
- 変更が依存関係チェーンを伝播する

主な違いは？veriqは適切な型と要求トレーサビリティを持つ複雑なエンジニアリング計算を処理できることです。

## チュートリアル：衛星の熱-電力解析の構築

簡単な衛星サブシステム解析を段階的に構築しましょう。熱を発生するソーラーパネルをモデル化し、温度が制限内に収まることを検証します。

### ステップ1：プロジェクト構造を作成する

新しいPythonファイル`my_satellite.py`を作成：

```python
import veriq as vq
from pydantic import BaseModel
from typing import Annotated

# プロジェクトを作成（新しいワークブックを作成するように）
project = vq.Project("MySatellite")

# スコープを作成（シートを作成するように）
power = vq.Scope("Power")
thermal = vq.Scope("Thermal")

# プロジェクトにスコープを追加
project.add_scope(power)
project.add_scope(thermal)
```

### ステップ2：設計モデルを定義する（入力セル）

設計モデルは提供する入力パラメータです。Pydanticモデルを使用して定義します：

```python
# Powerサブシステムが必要とするデータを定義
@power.root_model()
class PowerModel(BaseModel):
    solar_panel_area: float  # 平方メートル単位
    solar_panel_efficiency: float  # 0.0から1.0

# Thermalサブシステムが必要とするデータを定義
@thermal.root_model()
class ThermalModel(BaseModel):
    pass  # この例では入力は不要
```

### ステップ3：計算を追加する（数式セル）

計算はスプレッドシートの数式のようなものです。入力を受け取り、出力を計算します：

```python
# 計算の出力を定義
class SolarPanelOutput(BaseModel):
    power_generated: float  # ワット単位
    heat_generated: float  # ワット単位

# Powerスコープに計算を作成
@power.calculation()
def calculate_solar_panel(
    solar_panel_area: Annotated[float, vq.Ref("$.solar_panel_area")],
    solar_panel_efficiency: Annotated[float, vq.Ref("$.solar_panel_efficiency")],
) -> SolarPanelOutput:
    """ソーラーパネルからの電力と熱を計算する。"""
    # 1000 W/m²の太陽放射を仮定
    power_in = solar_panel_area * 1000.0
    power_out = power_in * solar_panel_efficiency
    heat_out = power_in - power_out

    return SolarPanelOutput(
        power_generated=power_out,
        heat_generated=heat_out,
    )
```

**`vq.Ref()`アノテーションに注目：**

- `"$"`は「現在のスコープのルート」を意味します
- `"$.solar_panel_area"`は「Powerモデルのsolar_panel_areaフィールド」を意味します

次に、電力計算結果を使用する熱計算を追加します：

```python
class ThermalOutput(BaseModel):
    solar_panel_temperature: float  # 摂氏

@thermal.calculation(imports=["Power"])
def calculate_temperature(
    heat_generated: Annotated[
        float,
        vq.Ref("@calculate_solar_panel.heat_generated", scope="Power")
    ],
) -> ThermalOutput:
    """発生した熱に基づいて温度を計算する。"""
    # 簡略化された熱モデル
    temperature = heat_generated * 0.05  # ワットあたり0.05°C
    return ThermalOutput(solar_panel_temperature=temperature)
```

**新しい概念：**

- `imports=["Power"]`は、この計算がPowerスコープからのデータを必要とすることをveriqに伝えます
- `scope="Power"`は、参照される値を探す場所を指定します
- `"@calculate_solar_panel"`は計算を参照します（`@`プレフィックスを使用）

### ステップ4：検証を追加する（要求チェック）

検証は、値が要求を満たすかをチェックする条件付き書式ルールのようなものです：

```python
@thermal.verification(imports=["Power"])
def solar_panel_temperature_limit(
    temperature: Annotated[
        float,
        vq.Ref("@calculate_temperature.solar_panel_temperature")
    ],
) -> bool:
    """ソーラーパネルの温度が制限内であることを検証する。"""
    MAX_TEMP = 85.0  # 摂氏
    return temperature <= MAX_TEMP
```

### ステップ5：入力ファイルを作成する

設計パラメータを含むTOMLファイル`my_satellite.in.toml`を作成：

```toml
[Power.model]
solar_panel_area = 2.0
solar_panel_efficiency = 0.3

[Thermal.model]
# 入力は不要
```

### ステップ6：プロジェクトをチェックする

プロジェクト構造が有効であることを確認：

```bash
veriq check my_satellite.py
```

次のように表示されます：

```
Loading project from script: my_satellite.py
Project: MySatellite

Validating dependencies...

╭──────────────────────── Project: MySatellite ────────────────────────╮
│ ┏━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓                           │
│ ┃ Scope   ┃ Calculations ┃ Verifications ┃                           │
│ ┡━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩                           │
│ │ Power   │            1 │             0 │                           │
│ │ Thermal │            1 │             1 │                           │
│ └─────────┴──────────────┴───────────────┘                           │
╰────────────────────────────────────────── 2 scopes ──────────────────╯

✓ Project is valid
```

### ステップ7：計算と検証を実行する

すべての結果を計算し、要求を検証：

```bash
veriq calc my_satellite.py -i my_satellite.in.toml -o my_satellite.out.toml --verify
```

次のように表示されます：

```
Loading project from script: my_satellite.py
Project: MySatellite

Loading input from: my_satellite.in.toml
Evaluating project...

╭──────────────────── Verification Results ────────────────────╮
│  Verification                                Result          │
│  Thermal::?solar_panel_temperature_limit     ✓ PASS          │
╰───────────────────────────────────────────────────────────────╯

Exporting results to: my_satellite.out.toml

✓ Calculation complete
```

### ステップ8：結果を確認する

`my_satellite.out.toml`を開いてすべての計算値を確認：

```toml
[Power.model]
solar_panel_area = 2.0
solar_panel_efficiency = 0.3

[Power.calc.calculate_solar_panel]
power_generated = 600.0
heat_generated = 1400.0

[Thermal.calc.calculate_temperature]
solar_panel_temperature = 70.0

[Thermal.verification]
solar_panel_temperature_limit = true
```

出力ファイルには以下が含まれます：

- すべての入力値（model）
- すべての計算値（calc）
- すべての検証結果（verification）

## 基本概念リファレンス

### プロジェクトとスコープ

**Project**は最上位のコンテナです。**Scope**はシステムを論理的なサブシステムに整理します：

```python
project = vq.Project("SatelliteName")

# 異なるサブシステム用のスコープを作成
power = vq.Scope("Power")
thermal = vq.Scope("Thermal")
structure = vq.Scope("Structure")

project.add_scope(power)
project.add_scope(thermal)
project.add_scope(structure)
```

### モデル（設計パラメータ）

**Model**は、Pydanticを使用して各スコープの入力データ構造を定義します：

```python
@power.root_model()
class PowerModel(BaseModel):
    battery_capacity: float  # ワット時単位
    solar_panel_area: float  # 平方メートル単位
```

### 計算

**Calculation**は派生値を計算する関数です。依存関係を自動的に追跡します：

```python
class BatteryOutput(BaseModel):
    max_discharge_power: float

@power.calculation()
def calculate_battery_performance(
    capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> BatteryOutput:
    max_power = capacity * 0.5  # 例：0.5Cの放電レート
    return BatteryOutput(max_discharge_power=max_power)
```

### 検証

**Verification**は要求が満たされているかをチェックします。合格の場合は`True`、不合格の場合は`False`を返します：

```python
@power.verification()
def verify_battery_capacity(
    capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> bool:
    MIN_CAPACITY = 100.0  # Wh
    return capacity >= MIN_CAPACITY
```

### 参照（`vq.Ref`）

参照は、データがどこにあるかをveriqに伝えます。構文は以下の通り：

- `"$"` - 現在のスコープモデルのルート
- `"$.field.subfield"` - モデル構造をナビゲート
- `"@calculation_name.output_field"` - 計算出力を参照
- `scope="ScopeName"` - 別のスコープを参照
- `imports=["ScopeName"]` - スコープの依存関係を宣言

例：

```python
vq.Ref("$.battery_capacity")  # 現在のスコープのモデル
vq.Ref("@calculate_power.max_power")  # 現在のスコープの計算
vq.Ref("$.battery_capacity", scope="Power")  # 別のスコープのモデル
vq.Ref("@calculate_temp.max_temp", scope="Thermal")  # 別のスコープの計算
```

### テーブル（多次元データ）

列挙型（動作モードなど）でインデックス付けされたデータには**Table**を使用します：

```python
from enum import StrEnum

class OperationMode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"

class PowerModel(BaseModel):
    # 動作モードでインデックス付けされたテーブル
    power_consumption: vq.Table[OperationMode, float]
```

TOMLファイル内：

```toml
[Power.model.power_consumption]
nominal = 50.0
safe = 10.0
```

多次元テーブルの場合：

```python
class OperationPhase(StrEnum):
    LAUNCH = "launch"
    ORBIT = "orbit"

class PowerModel(BaseModel):
    # (フェーズ、モード)でインデックス付けされたテーブル
    peak_power: vq.Table[tuple[OperationPhase, OperationMode], float]
```

TOMLファイル内：

```toml
[Power.model.peak_power]
"launch,nominal" = 100.0
"launch,safe" = 20.0
"orbit,nominal" = 80.0
"orbit,safe" = 15.0
```

## CLIリファレンス

### `veriq check`

計算を実行せずにプロジェクト構造が有効であることを確認：

```bash
# Pythonスクリプトをチェック
veriq check my_satellite.py

# モジュールをチェック（パッケージとしてインストールされている場合）
veriq check my_package.my_satellite:project

# プロジェクト変数を明示的に指定
veriq check my_satellite.py --project my_project

# 詳細モード
veriq --verbose check my_satellite.py
```

### `veriq calc`

計算を実行し、オプションで要求を検証：

```bash
# 基本的な計算
veriq calc my_satellite.py -i input.toml -o output.toml

# 検証付き
veriq calc my_satellite.py -i input.toml -o output.toml --verify

# モジュールパスを使用
veriq calc my_package.my_satellite:project -i input.toml -o output.toml

# 詳細モード
veriq --verbose calc my_satellite.py -i input.toml -o output.toml
```

**オプション：**

- `-i, --input`: 入力TOMLファイルへのパス（必須）
- `-o, --output`: 出力TOMLファイルへのパス（必須）
- `--verify`: 検証を実行し、失敗した場合はエラーで終了
- `--project`: プロジェクト変数の名前（スクリプトパスの場合のみ）
- `--verbose`: 詳細なデバッグ情報を表示

**終了コード：**

- `0`: 成功（計算完了、`--verify`使用時はすべての検証に合格）
- `1`: 失敗（検証失敗、またはエラーが発生）

## 高度な例

以下を示す完全な例については、[examples/dummysat.py](examples/dummysat.py)を参照してください：

- 複数の相互接続されたスコープ
- スコープ間の計算
- 複雑な検証
- 多次元データのテーブル使用
- 要求の定義とトレーサビリティ

## 開発状況

このプロジェクトは活発に開発中です。現在の機能：

- ✅ プロジェクト、スコープ、モデルの定義
- ✅ 自動依存関係追跡による計算の作成
- ✅ 検証の定義と実行
- ✅ TOML経由での設計データのエクスポート/インポート
- ✅ プロジェクトのチェックと計算実行のためのCLI
- 🚧 要求トレーサビリティ（部分的）
- 🚧 依存関係グラフの可視化

## 貢献

貢献を歓迎します！このプロジェクトは初期開発段階であり、APIが変更される可能性があることに注意してください。

## ライセンス

MIT License

## 謝辞

veriq は `shunichironomura/veriq` リポジトリで開発が始まり、v0.0.1 までの初期開発は ArkEdge Space Inc. の支援を受けて進められました。
