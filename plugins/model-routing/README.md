# model-routing

Fable 司令塔 + Opus/Sonnet モデル振り分け構成のプラグイン。

タスクの難易度に応じてモデルを使い分けることを目的としています。メイン会話は Fable が司令塔として受け口になり、実作業は Opus の `work-lead` に委譲、仕様が固まったサブタスクは Sonnet の `coder` が処理します。

## エージェント

| エージェント | モデル | 役割 |
| --- | --- | --- |
| （メイン会話） | Fable | 司令塔。タスクを受け取り `work-lead` に委譲する。直接扱うのは、`work-lead` が複数回失敗した問題と、アーキテクチャ全体に関わる設計判断のみ。 |
| `work-lead` | Opus | 実装・調査・バグ修正など大半のタスクの受け皿。タスクを分解し、設計判断・曖昧さの解消・成果物の検証を担う。Agent ツールを含む全ツールを利用可能。 |
| `coder` | Sonnet | 仕様が明確な実装・単純な修正・簡単なコード調査。Read / Edit / Write / Bash / Grep / Glob のみ。 |

## 委譲フロー

```
main (Fable)
  └─ work-lead (Opus)        タスク分解・設計判断・検証
       └─ coder (Sonnet)     仕様が明確なサブタスクの実装
```

- `main → work-lead`: 原則すべてのタスク。
- `work-lead → coder`: 仕様が明確なサブタスク。曖昧さが残るものは `work-lead` が自分で処理する。
- `coder` は仕様外の判断が必要になったら作業を止めて `work-lead` に報告する。

## インストール

```bash
claude plugin marketplace add yuki-eto/claude-plugins
```

```
/plugin install model-routing@yuki-eto-plugins
```

インストール後、ワークリポジトリの `CLAUDE.md` に委譲ポリシーを記載すると、メイン会話が自動的に `work-lead` へ委譲するようになります。テンプレートはリポジトリルートの README を参照してください。
