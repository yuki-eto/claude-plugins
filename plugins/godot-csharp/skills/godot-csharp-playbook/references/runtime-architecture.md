# ランタイム設計

## レイヤー

```
┌──────────────────────────── MyGame.csproj (Godot) ───────────────────────────┐
│ Autoload/GameApp     Scenes/*Screen  Scenes/*View   Audio/Godot*   *Loader    │
│   (共有サービス)       (画面)          (描画)          (IXxx の実装)   (I/O)       │
└───────────────┬───────────────────────────────┬──────────────────────────────┘
                │ 参照                           │ 参照
┌───────────────▼──────────── MyGame.Core ──────┐  ┌──── MyGame.Native ────┐
│ ルール / 状態機械 / タイミング計算 / DTO の検証  │  │ DllImport / ObjC 呼出  │
│ IBeatClock・ISfx・IRandomSource などの interface │  │ (Godot・Core に非依存) │
└───────────────────────────────────────────────┘  └───────────────────────┘
```

## Core に置くもの、App に置くもの

- **Core**: `Node` / `AudioServer` / `DisplayServer` / 描画に触らないもの全部。ルール、スコア計算、スポーン、難易度、タイミングの数式、設定値の検証・clamp、HUD 文字列の整形など
- **App**: Node のライフサイクル、入力の受け取り、描画、オーディオプレイヤー、ファイル I/O
- エンジンのハンドル（時計・プレイヤーなど）はコンストラクタかメソッドの引数で受け取る。ロジックのクラスの中から Godot のシングルトンを直接取りに行かない

### エンジン境界の interface

Core のクラスがエンジンの状態を必要とするときは、**必要なメソッドだけを持つ小さな interface** を Core 側に定義する。具象の Godot 型には依存させない。

```csharp
// Core
public interface IBeatClock
{
    double SongTime { get; }
    double QuantizeToGrid(double t, int division);
}

public sealed class SpawnSystem(IBeatClock clock, ISfx sfx, IRandomSource random) { ... }

// App
public partial class GodotSongClock : Node, IBeatClock { ... }
```

テストでは fake を渡す。新しい Core クラスが外の状態を必要としたときも、このパターンに合わせる。

## Autoload とシーン遷移

- Autoload は **`GameApp` 1 つ**にまとめる。アプリ全体で共有するものをここに置く
  - 起動時に読み込んだ設定、マスターデータ
  - 共有するプレイヤー（SE・BGM・ボイス）と時計
  - 画面をまたいで渡す値（選択中のモード・ステージ ID など）
  - 毎フレームのポーリング（セーフエリアの変化、予約再生の発火など）と、それを知らせる C# event
- 画面の遷移は `GetTree().ChangeSceneToFile("res://Scenes/Xxx.tscn")` で行う。遷移先に渡す値は、遷移の前に `GameApp` のプロパティに入れておき、遷移先の `_Ready()` で読む
- `run/main_scene` はタイトル画面にする。本編は「タイトル → 選択画面 → 本編」の順に遷移させる
- 本編シーンの中で UI を重ねる場合は `CanvasLayer`（例: `UiLayer`）を 1 つ置き、リザルト・ポーズメニューはその下に入れる
- Autoload への参照は `GetNode<GameApp>("/root/GameApp")` で取る。`GameApp` の C# event を購読したら、`_ExitTree()` で解除する

## 永続化（ローダーの分け方）

ファイルの読み書きは Godot 側、検証は Core 側に分ける。

```
SettingsLoader (App)                          Settings (Core)
  FileAccess で user://settings.json を読む →  Load(SettingsDto? dto)
  source-gen の JsonSerializerContext で          値を clamp、欠けている値は既定値で補う
  デシリアライズ                                   I/O は一切しない（xUnit でテストできる）
```

| データ | 置き場所 | 読めなかったとき |
|---|---|---|
| 同梱のマスターデータ | `res://` | **例外を投げる**（同梱アセットが無いのはビルドの不備） |
| 設定・ハイスコアなどユーザーのデータ | `user://*.json` | **既定値で続行する**（壊れたセーブデータで起動できなくしない） |

ユーザーデータのローダーの骨格は次のとおり（`JsonException` は握りつぶして `null` を返し、Core 側で既定値にする）。

```csharp
private static T? ReadJson<T>(string path, JsonTypeInfo<T> typeInfo) where T : class
{
    if (!FileAccess.FileExists(path)) return null;
    using var file = FileAccess.Open(path, FileAccess.ModeFlags.Read);
    if (file == null) return null;
    try { return JsonSerializer.Deserialize(file.GetAsText(), typeInfo); }
    catch (JsonException) { return null; }
}
```

## JSON は source generation のみ

- **reflection ベースの `JsonSerializer.Deserialize<T>()` は使わない。** iOS の NativeAOT では trim によって壊れる。移植作業で最大のリスクだった
- 新しく JSON を扱うときは、アプリ・Core・テストのどこであっても `[JsonSerializable(typeof(XxxDto))] partial class XxxJsonContext : JsonSerializerContext` を用意して使う
- 例外: オーサリング用の CLI が手書きの JSON を編集する場合は、`JsonNode` で直接操作してよい（[project-setup.md](project-setup.md) の「アセットのマスター」）

## リソースの読み込み

- import 済みのリソースなら、`ResourceLoader.Load<AudioStream>()` は**同期的に**返る。WebAudio の `decodeAudioData` のような非同期の読み込みを待つ処理は不要
- SE などはコンストラクタでまとめて読み込んでおけばよい

## スレッド

- Node やエンジンの API はメインスレッドからだけ呼ぶ
- ワーカースレッドがエンジンの状態（曲の再生位置など）を必要とする場合は、メインスレッドが毎フレームその値と実時刻をロック付きの箱に書き込み、ワーカー側はそこから外挿する（[audio-timing.md](audio-timing.md) の `SongTimeAnchor`）
- 例外的にワーカーから Godot の API を呼ぶ場合は、呼ぶ API を最小限にし、メインスレッドからの呼び出しと同じロックで直列化する
- 重い処理（音声のデコード・解析など）は `Task.Run` に出し、遅延初期化には `Lazy<T>(..., LazyThreadSafetyMode.ExecutionAndPublication)` を使う
