---
name: godot-agent-driving
description: 起動中の Godot ゲームのウィンドウを、エージェントが macOS 上で操作・撮影するための手順（ウィンドウ単位のスクリーンショット、osascript による合成入力の癖）。ユーザーがその会話で自動操作やスクリーンショットを明示的に頼んだときだけ使う。通常の確認は「build + test を通し、起動したまま確認チェックリストを渡す」流れで行う。
---

# 起動中の Godot ウィンドウの操作・撮影（macOS）

**この手順は opt-in。** ユーザーがその会話で自動操作やスクリーンショットを明示的に頼んだときだけ使う。合成入力は不安定でトークンも多く消費するため、既定の確認方法は「`run.sh` で起動したまま、確認チェックリストを渡す」こと（`godot-csharp-playbook` skill の `references/agent-workflow.md`）。

## 前提

- `screencapture` と `osascript` は Claude Code のサンドボックス内では動かないことが多い（Apple Events や Launch Services が遮断される）。単独のコマンドとしてサンドボックスを外して実行する（他のコマンドと連結しない）
- System Events を使う合成入力には、ターミナル（または Claude のアプリ）へのアクセシビリティ権限が必要。権限が無ければユーザーに付与を頼む。権限の設定をエージェントが変えてはいけない

## スクリーンショットはウィンドウ単位で撮る

デスクトップ全体を撮ると、別のモニタや手前に来た別アプリが写り、Godot のウィンドウを撮れていないことに気付きにくい。

1. スクラッチ領域に使い捨ての venv を作り、`pyobjc-framework-Quartz` を入れる（macOS 同梱の Python には `Quartz` が入っていない）
2. Godot のウィンドウ ID を取る

```python
import Quartz
for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID):
    if w.get("kCGWindowOwnerName") == "Godot":
        print(w["kCGWindowNumber"], w.get("kCGWindowName"))
```

3. そのウィンドウだけを撮る

```bash
screencapture -l<windowID> -x <scratch>/shot.png
```

## 合成入力の癖

- **Godot の `Control` / `Button` に対する、座標指定の合成クリック（System Events の `click at {x, y}`）は不安定。** ホバーやフォーカスの移動としては届いても、`Button.Pressed` が発火しないことがある。ほかのウィンドウを並行して使っていると、途中でフォーカスが移って特に起きやすい
- `_UnhandledInput` で受ける生のタップ（フィールドへのタップなど）は比較的安定して届く
- フォーカスが有効なビルドなら、Tab でフォーカスを移して Return / Space（`key code 36` / `49`）で押すほうが確実。ただし、全 Control を `FocusMode = None` にしているプロジェクトではこの方法は使えない。その場合は、生のタップを使うか、一時的なデバッグ用のフックを入れる
- 操作する前に `set frontmost of process "Godot" to true` でウィンドウを前面に出す
- 操作の後のスクリーンショットに変化が無くても、すぐに「UI が壊れている」と判断しない。同じ操作を再試行する。それでも曖昧なら、呼ばれているはずの C# の箇所に一時的な `GD.Print()` を入れ、呼び出しが届いているかを確かめる（確認が済んだら必ず消す）

## 音量

- エージェントが自分で起動して試すときは、音量を下げた設定（例: 5% 程度）で起動する
- ユーザーに確認してもらうために起動するときは、ユーザーの音量設定に触らない

## 後片付け

- 試すために起動したウィンドウは、確認が終わったら終了する。ユーザーに渡すために起動したウィンドウは残す
- 一時的に入れたデバッグ出力やフックを消し、`git diff` で残っていないことを確認する
