# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Claude Code のプラグインマーケットプレイス `yuki-eto-plugins` のリポジトリ。

- `.claude-plugin/marketplace.json` — マーケットプレイスの定義。収録プラグインの一覧を持つ。
- `plugins/<name>/` — 各プラグインの実体。`.claude-plugin/plugin.json` をマニフェストとして持ち、必要に応じて `agents/` `commands/` `skills/` `hooks/` を置く。

収録プラグイン:

- `model-routing` — Opus 司令塔 + Fable エスカレーションのモデル振り分け構成。`coder` / `explorer` / `advisor` の 3 エージェントを提供する。
- `no-shell-edit` — フックのみのプラグイン。PreToolUse(Bash) で `hooks/guard.py` がコマンドを解析し、Bash をエディタ代わりに使う操作（単一ファイルへの `sed -i`、ファイルへのリダイレクト、インライン python の書き込み等）を deny して Edit / Write に誘導する。複数ファイルの一括 `sed -i` は許可、`patch` / `git apply` は ask。判定ロジックを変えたら `hooks/test_guard.py` にケースを追加する。

このリポジトリ自身の作業でも、ファイルの作成・変更は Edit / Write ツールで行う（シェルのリダイレクトや `sed -i` は使わない）。

## Validation

変更後は必ず実行する。

```bash
claude plugin validate .
claude plugin validate ./plugins/model-routing
claude plugin validate ./plugins/no-shell-edit
python3 -m unittest discover -s plugins/no-shell-edit/hooks -p 'test_*.py'
```

## Adding a Plugin

1. `plugins/<name>/` を作成し、`plugins/<name>/.claude-plugin/plugin.json` に `name` / `version` / `description` を書く。
2. `.claude-plugin/marketplace.json` の `plugins` 配列に `name` / `source`（`./plugins/<name>`）/ `description` を追加する。
3. `claude plugin validate .` と `claude plugin validate ./plugins/<name>` で検証する。
