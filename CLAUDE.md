# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Claude Code のプラグインマーケットプレイス `yuki-eto-plugins` のリポジトリ。

- `.claude-plugin/marketplace.json` — マーケットプレイスの定義。収録プラグインの一覧を持つ。
- `plugins/<name>/` — 各プラグインの実体。`.claude-plugin/plugin.json` をマニフェストとして持ち、必要に応じて `agents/` `commands/` `skills/` `hooks/` を置く。

現在収録しているのは `model-routing`（Fable 司令塔 + Opus/Sonnet のモデル振り分け構成。`work-lead` と `coder` の 2 エージェントを提供）のみ。

## Validation

変更後は必ず両方を実行する。

```bash
claude plugin validate .
claude plugin validate ./plugins/model-routing
```

## Adding a Plugin

1. `plugins/<name>/` を作成し、`plugins/<name>/.claude-plugin/plugin.json` に `name` / `version` / `description` を書く。
2. `.claude-plugin/marketplace.json` の `plugins` 配列に `name` / `source`（`./plugins/<name>`）/ `description` を追加する。
3. `claude plugin validate .` と `claude plugin validate ./plugins/<name>` で検証する。
