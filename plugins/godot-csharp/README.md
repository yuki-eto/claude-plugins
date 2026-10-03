# godot-csharp

Godot 4.x（.NET/C#）で iOS/macOS 向けのゲームを、Claude Code のエージェントと一緒に作るためのプラグイン。実プロジェクト（Godot 4.7 .NET のリズムゲーム）で得た、ゲームの中身に依存しない知見をまとめている。

## 含まれるもの

| 種類 | 名前 | 内容 |
|---|---|---|
| skill | `godot-csharp-playbook` | 指針本体。プロジェクト構成、ビルド/テスト、ランタイム設計、UI/入力/モバイル、オーディオ同期、ネイティブ連携と iOS 配布、エージェントでの開発ワークフロー、ハマりどころ一覧（`references/`）と雛形（`templates/`） |
| skill | `godot-agent-driving` | 起動中の Godot ウィンドウを操作・撮影する手順。ユーザーが明示的に頼んだときだけ使う |
| command | `/godot-new-project <GameName> [target-dir]` | 雛形から新規プロジェクトを作る（App / Core / Core.Tests、run.sh / export.sh、`project.godot`、CLAUDE.md、docs）。最初の build → import → test まで行う |
| hook | PreToolUse(Bash) | Godot プロジェクト（ルート直下か 1 階層下に `project.godot` がある）で、`dotnet build` / `dotnet test` にサンドボックス用のフラグ（`-m:1 -nodeReuse:false --disable-build-servers`）が無いと警告する。`dotnet test` に `--no-build` が無い場合も警告する。実行は止めない |

## インストール

```
/plugin install godot-csharp@yuki-eto-plugins
```

## 前提

- Godot 4.x の .NET（mono）ビルド、.NET 8 以上、macOS の開発機
- iOS 向けには Xcode が必要
- `model-routing` プラグインとの併用を想定した記述がある（`references/agent-workflow.md`）。単独でも使える

## 検証

```bash
claude plugin validate ./plugins/godot-csharp
python3 -m unittest discover -s plugins/godot-csharp/hooks -p 'test_*.py'
```
