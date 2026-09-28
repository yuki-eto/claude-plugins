# model-routing

Opus 司令塔 + Fable エスカレーション構成のプラグイン。

タスクの難易度に応じてモデルを使い分けることを目的としています。メイン会話（Opus）が計画・設計判断・成果物の検証を担い、仕様が明確な実装は Sonnet の `coder`、機械的な探索は Haiku の `explorer` に委譲します。行き詰まったときだけ Fable の `advisor` に相談します。

メイン会話のモデルはプラグインでは指定できないため、`/model` で Opus に設定して使う前提です。

## エージェント

| エージェント | モデル | 役割 |
| --- | --- | --- |
| （メイン会話） | Opus | 司令塔。計画・設計判断・成果物の検証を担い、実作業は `coder` / `explorer` に委譲する。行き詰まったら `advisor` にエスカレーションする。 |
| `coder` | Sonnet | 仕様が明確な実装・単純な修正・簡単なコード調査。Read / Edit / Write / Bash / Grep / Glob に加え、`explorer` 呼び出し用の Agent を持つ。 |
| `explorer` | Haiku | コードベースの探索・検索専用。ファイルや関数の所在特定、使用箇所の洗い出し、依存関係の列挙などの機械的な調査。読み取り専用（Read / Grep / Glob / Bash）で、原因分析や設計判断はしない。メイン会話・`coder`・`advisor` のどこからでも呼び出せる。 |
| `advisor` | Fable | 読み取り専用の相談役。Read / Grep / Glob / Bash と、`explorer` 呼び出し専用の Agent を持つ。行き詰まった問題の根本原因と修正方針を返し、ファイルは変更しない。 |

Agent ツールで委譲する際の `subagent_type` は、プラグインプレフィックス付きのフルネーム（`model-routing:coder` / `model-routing:explorer` / `model-routing:advisor`）で指定する必要があります。

## 委譲フロー

```
main (Opus)                  計画・設計判断・成果物の検証
  ├─ explorer (Haiku)        機械的な探索・検索
  ├─ coder (Sonnet)          仕様が明確な実装
  │    └─ explorer (Haiku)   実装に必要な所在特定・使用箇所の洗い出し
  └─ advisor (Fable)         行き詰まったときだけ呼ぶ相談役
       └─ explorer (Haiku)   分析に必要な機械的な探索
```

- `main → explorer`: 所在特定・使用箇所の洗い出しなどの機械的な探索。メイン会話が自分でコードベースを広く読み回らない。
- `main → coder`: 仕様が明確な実装・単純な修正。委譲時は対象ファイル・期待する変更・完了条件を具体的に伝え、戻ってきた成果物はメイン会話が必ず検証する（差分確認・テスト実行）。探索結果（パス・行番号）はそのまま引き継ぎ、二重に探索させない。仕様が曖昧な部分は `coder` に投げずメイン会話で判断する。
- `main → advisor`: 次のいずれかに当てはまったときのエスカレーション。問題・試したこと・失敗内容・関連パスを渡す。
  - 同じ問題で修正→検証が 2 回失敗した
  - 仮説が尽きて原因を特定できない
  - アーキテクチャ全体に関わる設計判断
- `advisor` が返した修正方針をもとに、メイン会話が実装を `coder` に委譲する。
- `coder → explorer` / `advisor → explorer`: 作業に必要な機械的な探索。`coder` と `advisor` が Agent ツールで呼び出せるのは `explorer` のみ。
- `explorer` は読み取り専用で、どこから呼ばれても事実の報告に徹する。
- `coder` は仕様外の判断が必要になったら作業を止めて呼び出し元に報告する。

## インストール

```bash
claude plugin marketplace add yuki-eto/claude-plugins
```

```
/plugin install model-routing@yuki-eto-plugins
```

インストール後、ワークリポジトリの `CLAUDE.md` に委譲ポリシーを記載すると、メイン会話がそれに従って各エージェントへ委譲するようになります。テンプレートはリポジトリルートの README を参照してください。
