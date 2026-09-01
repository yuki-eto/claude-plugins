# model-routing

Fable 司令塔 + Opus/Sonnet モデル振り分け構成のプラグイン。

タスクの難易度に応じてモデルを使い分けることを目的としています。メイン会話は Fable が司令塔として受け口になり、実作業は Opus の `work-lead` に委譲、仕様が固まったサブタスクは Sonnet の `coder` が処理します。

## エージェント

| エージェント | モデル | 役割 |
| --- | --- | --- |
| （メイン会話） | Fable | 司令塔。タスクを受け取り `work-lead` に委譲する。直接扱うのは、`work-lead` が複数回失敗した問題と、アーキテクチャ全体に関わる設計判断のみ。 |
| `work-lead` | Opus | 実装・調査・バグ修正など大半のタスクの受け皿。タスクを分解し、設計判断・曖昧さの解消・成果物の検証を担う。Agent ツールを含む全ツールを利用可能。 |
| `coder` | Sonnet | 仕様が明確な実装・単純な修正・簡単なコード調査。Read / Edit / Write / Bash / Grep / Glob に加え、`explorer` 呼び出し用の Agent を持つ。 |
| `explorer` | Haiku | コードベースの探索・検索専用。ファイルや関数の所在特定、使用箇所の洗い出し、依存関係の列挙などの機械的な調査。読み取り専用（Read / Grep / Glob / Bash）で、原因分析や設計判断はしない。メイン会話・`work-lead`・`coder` のどこからでも呼び出せる。 |

Agent ツールで委譲する際の `subagent_type` は、プラグインプレフィックス付きのフルネーム（`model-routing:work-lead` / `model-routing:coder` / `model-routing:explorer`）で指定する必要があります。

## 委譲フロー

```
main (Fable)
  ├─ explorer (Haiku)        委譲前の所在確認など、機械的な探索・検索
  └─ work-lead (Opus)        タスク分解・設計判断・検証
       ├─ explorer (Haiku)   機械的な探索・検索
       └─ coder (Sonnet)     仕様が明確なサブタスクの実装
            └─ explorer (Haiku)   実装に必要な所在特定・使用箇所の洗い出し
```

- `main → work-lead`: 原則すべてのタスク。
- `main → explorer`: 委譲先を決めるための所在確認や、質問に答えるだけの簡単な調査など、機械的な探索。メイン会話が自分でコードベースを読み回らない。
- `work-lead → coder`: 仕様が明確なサブタスク。曖昧さが残るものは `work-lead` が自分で処理する。
- `work-lead → explorer`: 所在特定・使用箇所の洗い出しなどの機械的な調査。`work-lead` が自分でコードベースを読み回る前にまず委譲し、Opus の消費を抑える。
- `coder → explorer`: 実装に必要な所在特定・使用箇所の洗い出し。`coder` が Agent ツールで呼び出せるのは `explorer` のみで、`coder` / `work-lead` への再委譲はしない。
- `explorer` は読み取り専用で、どこから呼ばれても事実の報告に徹する。
- `coder` は仕様外の判断が必要になったら作業を止めて `work-lead` に報告する。

## インストール

```bash
claude plugin marketplace add yuki-eto/claude-plugins
```

```
/plugin install model-routing@yuki-eto-plugins
```

インストール後、ワークリポジトリの `CLAUDE.md` に委譲ポリシーを記載すると、メイン会話が自動的に `work-lead` へ委譲するようになります。テンプレートはリポジトリルートの README を参照してください。
