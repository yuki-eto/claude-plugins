# ビルド・起動・テスト

## Godot の起動方法

- **.NET 版 Godot は symlink 経由では起動できない。** GodotSharp のアセンブリを symlink の場所を基準に探すため、「.NET assemblies not found」で落ちる
- 実バイナリ（`/Applications/Godot_mono.app/Contents/MacOS/Godot`）を直接呼ぶか、`/usr/local/bin/godot` を次のようなラッパースクリプトにする

```bash
#!/bin/sh
exec /Applications/Godot_mono.app/Contents/MacOS/Godot "$@"
```

- スクリプト側では `GODOT_BIN="${GODOT_BIN:-/Applications/Godot_mono.app/Contents/MacOS/Godot}"` のように環境変数で上書きできるようにしておく

## 実行順序: build → import → launch/export

1. `dotnet build godot/MyGame.sln`
2. `godot --headless --path godot --import`
3. `godot --path godot`（起動）または `--export-debug` / `--export-release`

- **一度もビルドしていない C# プロジェクトを import すると、symlink のときと同じ assemblies-not-found で落ちる。** clone 直後や `.godot/` を消した後は、必ずビルドを先に行う
- import はアセットや import 設定を変えるたびに必要になる。`.godot/`（キャッシュ）も再生成されるので gitignore に入れる
- この順序は手で守らせず、スクリプトにする
  - [templates/run.sh](../templates/run.sh): build → import → 起動
  - [templates/export.sh](../templates/export.sh): テンプレートの確認 → build → import → export → iOS の後処理

## サンドボックス（Claude Code の Seatbelt）での注意

エージェントが Bash ツールから実行するときに効く。

| コマンド | 症状 | 対処 |
|---|---|---|
| `dotnet build` | ちょうど 5 分固まった後、「0 エラー」で失敗する（MSBuild のノード間 IPC が遮断される） | **`-m:1 -nodeReuse:false --disable-build-servers`** を付ける。サンドボックス内のまま約 10 秒で通る |
| `dotnet test` | `SocketException (13): Permission denied`（vstest が testhost とループバック TCP で通信する） | 上と同じフラグに `--no-build` を付け、**サンドボックスを外して**実行する |
| `godot ...`（import/export/起動） | 出力も CPU 使用もないまま止まる | サンドボックスを外して実行する |

### サンドボックスを外す範囲

- 外してよいのは `dotnet test ... --no-build`、`godot ...`、`tools/run.sh`、`tools/export.sh` だけにする。`dotnet build` / `dotnet run` / `dotnet tool` などはサンドボックス内で実行する
- `dotnet test` には必ず `--no-build` を付け、先にサンドボックス内で `dotnet build` を通す。付けないとビルドと NuGet の restore まで外で走り、パッケージ内の `.targets` やアナライザがサンドボックスの外で動く
- `tools/run.sh` / `tools/export.sh` は内部で `dotnet build` も実行するため、外して動かすとビルドと restore も外で走る。パッケージを追加・更新した直後は、先にサンドボックス内で `dotnet build` を通して restore を済ませてから実行する
- 単独のコマンドとして実行する。外す指定はコマンドライン全体に効くので、`cd ... && rm ... && dotnet test` のように連結すると、連結したコマンドも外で動く
- Godot の `--import` や起動では、プロジェクト内の `[Tool]` クラス、EditorPlugin、`addons/` がサンドボックスの外で動く。サードパーティのアドオンや NuGet パッケージを追加するときは、ユーザーに確認する

サブエージェントに渡す brief には、ビルドのフラグを必ず書く（書かないと「ビルド待ち」で止まる）。このプラグインの hook は、Godot プロジェクト（ルート直下か 1 階層下に `project.godot` がある）で、フラグの欠けた `dotnet build` / `dotnet test` や、`--no-build` の無い `dotnet test` が実行されそうになると警告する。実行は止めない。

## テストの方針

### Core は xUnit、Godot 依存部分は人間が確認する

- Core のロジックには、使い捨てのスクリプトではなく xUnit のテストを書く。`dotnet test` は Godot ランタイムなしで動く高速なループになる
- シーン・Autoload など Godot に依存するコードは、ビルドして起動し、人間が確認する。ネイティブ側のエラー（三角形分割の失敗など）は `dotnet test` では捕まらず、実際に起動しないと分からない

### テストしやすくするための設計

- **乱数は注入する。** `IRandomSource` を受け取る形にし、static の `Random.Shared` などを直接呼ばない。テストでは決まった値の列を返す `SequenceRandomSource` を渡し、乱数を消費する**順序**まで検証する。同じ乱数列を共有すべきシステム同士には同じインスタンスを渡す
- **エンジンとの境界は小さな interface にする**（例: `IBeatClock`、`ISfx`）。テストでは小さな fake で置き換える
- **描画に使うロジックも純粋関数として Core に切り出す。** HUD の文字列整形、音量のエンベロープ、優先度判定などは、Godot から切り離せば普通にテストできる

### ゴールデン / テストベクター

移植元（あるいは別ツール）の出力と突き合わせたいときのパターン。

- 入力と期待出力の組を JSON に書き出し、C# 側の `[Theory]` でその JSON を読んで全件を検証する
- JSON はテストプロジェクトの `Content` として出力ディレクトリにコピーし、`AppContext.BaseDirectory` から読む。テストランナーのカレントディレクトリに依存させない

```xml
<ItemGroup>
  <Content Include="Golden/**/*.json" CopyToOutputDirectory="PreserveNewest" />
</ItemGroup>
```

- 自前で持つゴールデンファイルは、`UPDATE_GOLDEN=1` のような環境変数を付けて実行したときだけ再生成するようにする
- テストのローダーも source generation の JSON を使う（本体と同じ規律を保つため）

## エクスポート

- `godot --headless --path godot --export-debug "<preset名>" <出力パス>`。preset 名は `export_presets.cfg` の `name=` と完全に一致させる（大文字小文字も区別される）
- Godot は出力先のディレクトリを作ってくれない（「target folder doesn't exist」で失敗する）。スクリプト側で `mkdir -p` しておく
- iOS 固有の手順は [native-ios.md](native-ios.md) を参照

## エージェントが起動した Godot ウィンドウについて

サブエージェントがバックグラウンドの Bash で起動したウィンドウは、そのエージェントのターンが終わると間もなく終了する。人間に確認してもらうために起動したまま渡すときは、メイン会話から `run_in_background` で `run.sh` を起動するか、人間に `run.sh` を実行してもらう。
