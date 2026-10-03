# プロジェクト構成

## ディレクトリ構成

```
repo/
  assets/                 … アセットのマスター（エンジン非依存。任意）
  docs/                   … 仕様・タスク・履歴（agent-workflow.md の「docs 運用」）
  godot/
    MyGame.sln
    MyGame.csproj         … Godot アプリ本体（Godot.NET.Sdk）
    project.godot
    export_presets.cfg
    Autoload/             … Autoload シングルトン（GameApp.cs のみが理想）
    Scenes/               … 画面ごとの .tscn と C# スクリプト
    Audio/                … Godot 側のオーディオ実装（Core の interface を実装する）
    assets/               … 生成物。assets/ マスターから同期する（手で編集しない）
    lib/                  … .gdignore を置く
      MyGame.Core/        … エンジン非依存のロジック（Microsoft.NET.Sdk）
      MyGame.Core.Tests/  … xUnit。Godot への参照なし
      MyGame.Native/      … P/Invoke 層（必要なときだけ）
    tools/                … .gdignore を置く。run.sh / export.sh / オーサリング CLI
    native/               … .NET 外のネイティブコード（Swift など）。.gdignore を置く
```

## .NET プロジェクトの分割

| プロジェクト | SDK | 役割 | 参照先 |
|---|---|---|---|
| `MyGame.csproj` | `Godot.NET.Sdk/<ver>` | Node・シーン・描画・オーディオなど、Godot に触る部分すべて | Core, Native |
| `MyGame.Core` | `Microsoft.NET.Sdk` | ルール・状態機械・タイミング計算・データ検証。`Node` / `AudioServer` / `DisplayServer` には触らない | なし |
| `MyGame.Core.Tests` | `Microsoft.NET.Sdk` + xUnit | Core（と Native のうち純粋な部分）のテスト | Core, Native, tools |
| `MyGame.Native` | `Microsoft.NET.Sdk` | `DllImport` / ObjC runtime の P/Invoke。Godot にも Core にも依存しない | なし |
| `tools/<Cli>` | `Microsoft.NET.Sdk` (Exe) | オーサリング用 CLI（アセット生成・同期など）。アプリには含めない | Core |

P/Invoke を Core ではなく Native に置くのは、Core をどの OS でも純粋にテストできる状態に保つため。

雛形: [templates/MyGame.csproj](../templates/MyGame.csproj)、[templates/MyGame.Core.csproj](../templates/MyGame.Core.csproj)、[templates/MyGame.Core.Tests.csproj](../templates/MyGame.Core.Tests.csproj)

### App csproj の必須設定

- **`<Compile Remove="lib/**/*.cs" />` と `<Compile Remove="tools/**/*.cs" />`**
  - SDK の既定の glob（`**/*.cs`）は `lib/` や `tools/` のソースもアプリのアセンブリにコンパイルしてしまう。`ProjectReference` と二重になるうえ、CLI の `Main` まで入る
  - `.gdignore` が止めるのは **エディタのファイルスキャンだけ**で、コンパイル対象からは外れない。両方とも必要
- **`<InvariantGlobalization>true</InvariantGlobalization>`**
  - iOS/NativeAOT では、Godot のエクスポートが `icudt.dat` を同梱しないため、ICU の初期化が起動時にクラッシュする（`GlobalizationNative_LoadICUData` の `strdup(NULL)`）
  - カルチャ依存の処理が要らないゲームなら最初から有効にする。数値のパース・整形には明示的に `CultureInfo.InvariantCulture` を渡す
- `<Nullable>enable</Nullable>`、`<TargetFramework>net8.0</TargetFramework>`

### Core / Native csproj の必須設定

- **`<IsAotCompatible>true</IsAotCompatible>`**: reflection や trim で壊れるコードをビルド時の警告で検出できる
- **`<Configurations>Debug;Release;ExportDebug;ExportRelease</Configurations>`**: Godot のソリューション構成名に合わせる

### sln の構成

- ソリューション構成は Godot の慣例どおり `Debug` / `ExportDebug` / `ExportRelease` にする（素の `Release` は無い）
- **Tests は `Debug` でのみビルドする。** `ExportDebug` / `ExportRelease` では `ActiveCfg` だけを書き、`Build.0` を書かない。こうするとテストコードがエクスポートに混ざらない

## project.godot の推奨設定

雛形: [templates/project.godot.sample](../templates/project.godot.sample)

| キー | 値 | 理由 |
|---|---|---|
| `application/run/main_scene` | タイトル画面 | ゲーム本編のシーンをいきなり起動しない。画面間の値は Autoload 経由で受け渡す |
| `autoload/GameApp` | `"*res://Autoload/GameApp.cs"` | Autoload は 1 つにまとめる（[runtime-architecture.md](runtime-architecture.md)） |
| `display/window/stretch/mode` | `"canvas_items"` | UI を論理座標で組むため |
| `display/window/stretch/aspect` | `"expand"` | 端末の画面全体を使う。`keep` にすると縦横比の違う端末で黒帯が出る。縦横比の違いは `UiFrame` で吸収する（[ui-input-mobile.md](ui-input-mobile.md)） |
| `display/window/size/viewport_*` | 縦長なら 1080x1920 など | 基準解像度 |
| `display/window/size/window_*_override` | 540x960 など | デスクトップで起動したときの初期ウィンドウサイズ。実際のサイズは起動時にコードで決める |
| `display/window/handheld/orientation` | **整数**（`0`..`6`） | 下の注意を参照 |
| `input_devices/pointing/emulate_touch_from_mouse` | `true` | デスクトップでもタッチイベント 1 種類で処理するため |
| `rendering/renderer/rendering_method` | `"mobile"` | iOS 向け |
| `application/run/max_fps` | `0` | 上限は設定画面などから `Engine.MaxFps` で決める |

**orientation は Godot 4 では整数の enum**（`Landscape, Portrait, Reverse Landscape, Reverse Portrait, Sensor Landscape, Sensor Portrait, Sensor` = `0..6`）。Godot 3 時代の文字列（`"portrait"`）を書くと、何も言われずに `0`（Landscape）として読まれ、iOS の `Info.plist` が横向きになる。縦横両対応にするなら `6`（Sensor）にして plist に 4 方向すべてを出し、実際の向きは起動時に `DisplayServer.ScreenSetOrientation()` で固定する（iOS は plist と実行時指定の**共通部分**を採用する）。

## Godot.NET.Sdk のバージョン

エディタより古い `Sdk="Godot.NET.Sdk/<ver>"` は、エディタ（headless の `--import` を含む）が自動で書き換え、`.csproj.old` というバックアップを残す。エディタを上げるたびに起きるので、意図した変更として csproj の差分をコミットし、`.old` は削除する。**export templates はエディタを上げても自動では入らない**（[native-ios.md](native-ios.md)）。

## アセットのマスターと生成コピー（任意）

アセットを複数の実装やツールで共有する場合の構成。

- マスターはリポジトリ直下の `assets/` に置く。`godot/assets/` は CLI の `sync` サブコマンドで生成する（音声の ogg 変換などもここで行う）
- `godot/assets/` は**丸ごと生成物**として扱い、手で編集しない
- 例外は `*.import` サイドカー。Godot の import 設定（git 管理）なので、手で編集してよい。sync はこれに触らない
- sync の後は `godot --headless --path godot --import` を実行する
- マスターの JSON をツールで更新するときは、型付き DTO で往復させず `JsonNode` のツリーを直接書き換える。DTO を経由すると、ツールが知らない手書きのフィールドが落ち、キーの順序も変わる
