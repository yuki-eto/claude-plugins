---
description: Godot 4.x (.NET/C#) の新規ゲームプロジェクトを godot-csharp-playbook の構成で作成する
argument-hint: <GameName> [target-dir]
---

# Godot C# プロジェクトの新規作成

引数: `$ARGUMENTS`

`godot-csharp-playbook` skill の構成（App / Core / Core.Tests、run.sh / export.sh、推奨設定の `project.godot`、CLAUDE.md、docs インデックス）で、新しいゲームプロジェクトを作る。まず `godot-csharp-playbook` skill の SKILL.md と `references/project-setup.md` を読んでから始める。

雛形は、このプラグインの `skills/godot-csharp-playbook/templates/` にある（`${CLAUDE_PLUGIN_ROOT}/skills/godot-csharp-playbook/templates/`。変数が展開されていなければ `~/.claude/plugins/` 配下で `godot-csharp` プラグインのディレクトリを探す）。

## 0. 引数と前提の確認

- 第 1 引数 `<GameName>` は PascalCase の名前（例: `StarRunner`）。ソリューション名・アセンブリ名・名前空間に使う。無ければユーザーに聞く
- 第 2 引数 `[target-dir]` はリポジトリのルート。省略したらカレントディレクトリ
- 次を確認し、問題があれば止めてユーザーに報告する
  - `<target-dir>/godot/project.godot` が既にある → 既存のプロジェクトを上書きしない
  - `dotnet --version` が 8 以上
  - Godot .NET の実バイナリ（既定は `/Applications/Godot_mono.app/Contents/MacOS/Godot`）がある。`which godot` が symlink なら、ラッパースクリプトにするよう案内する（自分では変更しない）

## 1. 計画を示して確認を取る

作成するファイルの一覧と、`MyGame` を `<GameName>` に置き換えることを示し、ユーザーの了承を得てから書き込む。

## 2. ファイルの作成

ファイルはすべて Write ツールで作る（雛形を Read して `MyGame` を置換した内容を Write する）。シェルのリダイレクトや `sed -i` で書かない。

| 作成先（`<target-dir>` からの相対パス） | 元 |
|---|---|
| `godot/<GameName>.csproj` | `templates/MyGame.csproj`（Native を使わないので、その ProjectReference はコメントのまま） |
| `godot/lib/<GameName>.Core/<GameName>.Core.csproj` | `templates/MyGame.Core.csproj` |
| `godot/lib/<GameName>.Core.Tests/<GameName>.Core.Tests.csproj` | `templates/MyGame.Core.Tests.csproj` |
| `godot/project.godot` | `templates/project.godot.sample`（`config/name` は表示名にする） |
| `godot/tools/run.sh`、`godot/tools/export.sh` | 同名の雛形。作成後に `chmod +x` |
| `godot/lib/.gdignore`、`godot/tools/.gdignore` | 空ファイル |
| `CLAUDE.md`、`godot/CLAUDE.md` | `templates/CLAUDE.md.template` の前半・後半（`<...>` を埋め、分からない箇所は残してユーザーに伝える） |
| `docs/README.md` | 空のインデックス（正となる文書 / 機能別タスク `features/` / 履歴 `PROGRESS.md` の 3 つの表） |
| `.gitignore` | `godot/.godot/`、`godot/build/`、`**/bin/`、`**/obj/`、`godot/native/bin/` |

最小限のソースも作る。中身は skill の references にあるコード例に沿わせる。

- `godot/Autoload/GameApp.cs`: `partial class GameApp : Node`。`SafeAreaChanged` イベントと、毎フレーム `DisplayServer.GetDisplaySafeArea()` を比較する処理（`references/ui-input-mobile.md`）
- `godot/Scenes/UiFrame.cs`、`godot/Scenes/SafeArea.cs`、`godot/Scenes/UiLayout.cs`（`FitToViewport` / `DisableFocus` / `WireBackdropDismiss`）: `references/ui-input-mobile.md` のコード例どおり。デザインサイズはユーザーに確認する（既定は縦長 540x960）
- `godot/Scenes/Title.tscn` と `godot/Scenes/TitleScreen.cs`: 全画面の背景と、その上の `UiFrame` に中央寄せの Label を 1 つ置くだけの画面
- `godot/lib/<GameName>.Core/Random/IRandomSource.cs` と、実装の `SystemRandomSource.cs`
- `godot/lib/<GameName>.Core.Tests/SmokeTests.cs`: Core を 1 つ参照するだけの xUnit テスト（テストの実行経路を確かめるため）

## 3. ソリューション

```bash
cd <target-dir>/godot && dotnet new sln -n <GameName>
```

- SDK が `.slnx` を作った場合は、`--format sln` を付けて作り直す（Godot は `.sln` を使う）
- `dotnet sln add` で 3 つの csproj を追加する
- sln のソリューション構成を `Debug` / `ExportDebug` / `ExportRelease` にし、各プロジェクトをそれに対応付ける。Tests は `ExportDebug` / `ExportRelease` では `ActiveCfg` の行だけを書き、`Build.0` を書かない（Edit ツールで編集する。`references/project-setup.md` の「sln の構成」）

## 4. ビルドと import

順序を守る（`references/build-test-tooling.md`）。

```bash
dotnet build godot/<GameName>.sln -m:1 -nodeReuse:false --disable-build-servers
```

```bash
<godot-bin> --headless --path godot --import
```

```bash
dotnet test godot/lib/<GameName>.Core.Tests/<GameName>.Core.Tests.csproj -m:1 -nodeReuse:false --disable-build-servers --no-build
```

- サンドボックスを外すのは `godot` の呼び出しと `dotnet test ... --no-build` だけにする。どれも単独のコマンドとして実行し、`&&` などで他のコマンドと連結しない（外す指定はコマンドライン全体に効く）
- import で csproj の `Godot.NET.Sdk` のバージョンが書き換わり、`.csproj.old` ができたら、`.old` を削除する
- 失敗したら、`references/pitfalls.md` を症状から引いて対処する

## 5. 完了報告

次をまとめて報告する。

- 作成したファイルの一覧と、build / import / test の結果
- 起動して確かめる方法（`godot/tools/run.sh`）
- 人間が行う残りの作業
  - `/usr/local/bin/godot` を、実バイナリを `exec` するラッパースクリプトにする（symlink は不可）
  - エディタで export preset（iOS / macOS）を作る。iOS では `application/app_store_team_id`、`bundle_identifier`、`export_project_only=true` を設定する
  - 使用中のエディタのバージョンに合う export templates を入れる
  - フォントを追加したら、`.ttf.import` で MSDF を有効にする
  - 縦横両対応にするなら、`project.godot` の orientation を `6` にし、`export.sh` の `REQUIRED_ORIENTATIONS` を更新する

git の commit はしない。
