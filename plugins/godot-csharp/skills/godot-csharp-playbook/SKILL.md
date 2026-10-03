---
name: godot-csharp-playbook
description: Godot 4.x (.NET/C#) で macOS/iOS 向けゲームを新規に立ち上げる・開発するときの指針。プロジェクト構成、ビルド/テスト手順、ランタイム設計、UI/入力/モバイル対応、オーディオ同期、ネイティブ連携と iOS 配布、Claude Code エージェントでの開発ワークフロー、既知のハマりどころをまとめる。Godot C# プロジェクトの作成・csproj や project.godot の設定変更・画面レイアウトや入力処理の実装・ビルドやエクスポートの失敗調査のときに使う。
---

# Godot C# Playbook

Godot 4.7 .NET で iOS/macOS 向けのゲームを作った実プロジェクトから、**ゲームの中身に依存しない知見**を抜き出した指針。

## 前提

- Godot 4.x の **.NET（mono）ビルド**。スクリプトはすべて C#（GDScript は使わない）。.NET 8 以上
- 開発機は macOS。配布先は iOS と macOS（Android は未検証）
- Claude Code のエージェントが実装し、人間が実機で動作を確認する体制

## 使い方

作業内容に合う章だけを読む。全章を最初に読む必要はない。何かがおかしいときは、まず [references/pitfalls.md](references/pitfalls.md) を症状から引く。

| 章 | いつ読むか |
|----|-----------|
| [references/project-setup.md](references/project-setup.md) | 新規プロジェクトを作るとき、csproj・sln・`project.godot` を触るとき |
| [references/build-test-tooling.md](references/build-test-tooling.md) | ビルド・起動・テストのコマンドを組むとき、ビルドが固まる・落ちるとき |
| [references/runtime-architecture.md](references/runtime-architecture.md) | ロジックの置き場所、シーン遷移、セーブデータ、スレッドを設計するとき |
| [references/ui-input-mobile.md](references/ui-input-mobile.md) | 画面レイアウト、解像度、セーフエリア、タップ入力、フォント、描画 |
| [references/audio-timing.md](references/audio-timing.md) | 音楽に同期させる処理、SE の予約再生、ループ再生（音ゲー・リズム要素がある場合のみ） |
| [references/native-ios.md](references/native-ios.md) | Swift/OS API との連携、iOS エクスポート、署名、実機への配布 |
| [references/agent-workflow.md](references/agent-workflow.md) | CLAUDE.md の書き方、サブエージェントへの委譲、検証の分担、docs 運用 |
| [references/pitfalls.md](references/pitfalls.md) | 何かおかしいとき最初に引く「症状 → 原因 → 対処」の一覧 |
| [templates/](templates/) | コピーして `MyGame` を置換する雛形（スクリプト、csproj、`project.godot`、CLAUDE.md、機能ドキュメント） |

新規プロジェクトの作成は `/godot-new-project <GameName>` コマンドで、このチェックリストを順に実行できる。

## 新規プロジェクト立ち上げチェックリスト

1. `templates/` から csproj 3 種と sln の構成を作る（[references/project-setup.md](references/project-setup.md)）
   - App / Core / Core.Tests（必要なら Native）に分ける
   - App の csproj に `<Compile Remove="lib/**/*.cs" />` と `InvariantGlobalization=true` を入れる
   - `lib/` と `tools/` に `.gdignore` を置く
2. `project.godot` に推奨設定を入れる（stretch=`canvas_items` + `expand`、orientation は**整数値**、`emulate_touch_from_mouse=true`）
3. `templates/run.sh` と `templates/export.sh` を `godot/tools/` に置き、`MyGame` を置換する
4. `/usr/local/bin/godot` を実バイナリを `exec` するラッパースクリプトにする（**symlink は不可**）
5. 初回は `dotnet build` → `godot --headless --import` の順で実行する
6. Autoload を 1 つ（`GameApp`）だけ登録し、タイトル画面を `run/main_scene` にする
7. 画面のルートに `UiFrame` と `SafeArea` を入れ、タップ処理を `InputEventScreenTouch` の 1 種類に絞る（[references/ui-input-mobile.md](references/ui-input-mobile.md)）
8. フォントは MSDF で import する
9. JSON はすべて source generation の `JsonSerializerContext` を使う
10. iOS を出す場合は、export templates の導入、`app_store_team_id` の設定、`export.sh` の署名パッチを用意する
11. `templates/CLAUDE.md.template` からリポジトリの CLAUDE.md を作り、`docs/README.md` のインデックスを置く

## 原則（どの章にも共通）

1. **ロジックはエンジン非依存の Core に置く。** Godot の型に触るのは App 層だけにし、Core は Godot なしの xUnit でテストする
2. **エンジンとの境界には最小限のインターフェースを置く。** 時計・SE・乱数などは Core 側に小さな interface を定義し、Godot 側で実装する
3. **trim/AOT で壊れるものを最初から使わない。** reflection ベースの JSON、カルチャ依存の処理（ICU）がこれに当たる
4. **順序が決まっている手順はスクリプトにする。** build → import → launch/export の順序を手作業に任せない
5. **生成物は手で直さない。** 生成元を直して再生成する（例外は Godot の `.import` サイドカー）
6. **エンジンの時刻は毎フレーム再計算した値を読む。** フレームの delta を積算しない（オーディオ同期を扱う場合）
7. **オプションのネイティブ機能は必ずフォールバックを用意する。** ライブラリが無くても起動・動作するようにする
8. **実機での確認は人間が行う。** エージェントは build + test が通るところまでを保証し、起動した状態と確認チェックリストを渡す

## 関連

- 同じプラグインの `godot-agent-driving` skill: 起動中の Godot ウィンドウをエージェントが操作・撮影する手順（ユーザーが明示的に頼んだときだけ使う）
- 同じプラグインの hook: サンドボックス内で `dotnet build` / `dotnet test` に必要なフラグが無いと警告する。`dotnet test` に `--no-build` が無い場合も警告する（[references/build-test-tooling.md](references/build-test-tooling.md)）

## 保守

- 記述は Godot 4.7.x / .NET 8 / Xcode 27 時点のもの。エンジンを上げたら、[references/pitfalls.md](references/pitfalls.md) の各項目がまだ再現するか見直す
- 新しい知見を足すときは、ゲーム固有の数値やクラス名を持ち込まず、「症状・原因・対処・発見の経緯」の形で書く
