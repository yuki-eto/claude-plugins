# model-routing

Opus 司令塔 + Fable エスカレーション構成のプラグイン。

タスクの難易度に応じてモデルを使い分けることを目的としています。メイン会話（Opus）が計画・設計判断・成果物の検証を担い、仕様が明確な実装は Sonnet の `coder`、機械的な探索は Haiku の `explorer` に委譲します。ユーザーに引き継ぐ前に Opus の `reviewer` で変更を点検し、行き詰まったときや念入りに見るべき箇所だけ Fable の `advisor` に相談します。

メイン会話のモデルはプラグインでは指定できないため、`/model` で Opus に設定して使う前提です。

## エージェント

| エージェント | モデル | 役割 |
| --- | --- | --- |
| （メイン会話） | Opus | 司令塔。計画・設計判断・成果物の検証を担い、実作業は `coder` / `explorer` に委譲する。行き詰まったら `advisor` にエスカレーションする。 |
| `coder` | Sonnet | 仕様が明確な実装・単純な修正・簡単なコード調査。Read / Edit / Write / Bash / Grep / Glob に加え、`explorer` 呼び出し用の Agent を持つ。 |
| `explorer` | Haiku | コードベースの探索・検索専用。ファイルや関数の所在特定、使用箇所の洗い出し、依存関係の列挙などの機械的な調査。読み取り専用（Read / Grep / Glob / Bash）で、原因分析や設計判断はしない。メイン会話・`coder`・`advisor` のどこからでも呼び出せる。 |
| `reviewer` | Opus | 引き継ぎ前の自動チェック役。実装が一段落した変更を点検し、仕様との食い違い・バグ・影響範囲・テスト不足を指摘する。Read / Grep / Glob / Bash と、`explorer` 呼び出し専用の Agent を持つ。ファイルは変更しない。判断しきれない箇所は「要精査」として返す。 |
| `advisor` | Fable | 読み取り専用の相談役。Read / Grep / Glob / Bash と、`explorer` 呼び出し専用の Agent を持つ。行き詰まった問題の根本原因と修正方針を返し、ファイルは変更しない。 |

Agent ツールで委譲する際の `subagent_type` は、プラグインプレフィックス付きのフルネーム（`model-routing:coder` / `model-routing:explorer` / `model-routing:reviewer` / `model-routing:advisor`）で指定する必要があります。

## 委譲フロー

```
main (Opus)                  計画・設計判断・成果物の検証
  ├─ explorer (Haiku)        機械的な探索・検索
  ├─ coder (Sonnet)          仕様が明確な実装
  │    └─ explorer (Haiku)   実装に必要な所在特定・使用箇所の洗い出し
  ├─ reviewer (Opus)         引き継ぎ前の自動チェック
  │    └─ explorer (Haiku)   影響範囲の洗い出し
  └─ advisor (Fable)         行き詰まったとき・要精査の箇所だけ呼ぶ相談役
       └─ explorer (Haiku)   分析に必要な機械的な探索
```

- `main → explorer`: 所在特定・使用箇所の洗い出しなどの機械的な探索。メイン会話が自分でコードベースを広く読み回らない。
- `main → coder`: 仕様が明確な実装・単純な修正。委譲時は対象ファイル・期待する変更・完了条件を具体的に伝え、戻ってきた成果物はメイン会話が必ず検証する（差分確認・テスト実行）。探索結果（パス・行番号）はそのまま引き継ぎ、二重に探索させない。仕様が曖昧な部分は `coder` に投げずメイン会話で判断する。
- `main → advisor`: 次のいずれかに当てはまったときのエスカレーション。問題・試したこと・失敗内容・関連パスを渡す。
  - 同じ問題で修正→検証が 2 回失敗した
  - 仮説が尽きて原因を特定できない
  - アーキテクチャ全体に関わる設計判断
- `advisor` が返した修正方針をもとに、メイン会話が実装を `coder` に委譲する。
- `main → reviewer`: 実装とテストが一段落し、ユーザーに引き継ぐ直前の自動チェック。変更範囲（diff の基点・対象ファイル）・仕様と完了条件・実行済みのテストを渡す。typo やドキュメントのみなど、ごく小さな変更では省略してよい。ユーザーから明示的に依頼されたコードレビューはメイン会話が行い、`reviewer` は使わない。
  - 指摘はメイン会話が検証し、修正は `coder` に委譲する。修正が大きければ再度 `reviewer` に通す。
  - 「要精査」として返った箇所は、メイン会話が `advisor` に回す。
- `coder → explorer` / `reviewer → explorer` / `advisor → explorer`: 作業に必要な機械的な探索。`coder` / `reviewer` / `advisor` が Agent ツールで呼び出せるのは `explorer` のみ。
- `explorer` は読み取り専用で、どこから呼ばれても事実の報告に徹する。
- `coder` は仕様外の判断が必要になったら作業を止めて呼び出し元に報告する。

## インストール

```bash
claude plugin marketplace add yuki-eto/claude-plugins
```

```
/plugin install model-routing@yuki-eto-plugins
```

インストールすれば、委譲ポリシーはセッション開始時に自動で注入されます。`CLAUDE.md` への記載は不要です。

## SessionStart での委譲ポリシー注入

`hooks/session_context.py` が SessionStart（startup / resume / clear / compact）で委譲ポリシーを `additionalContext` として出力し、メイン会話が上記の委譲フローに従うようにします。注入はメイン会話のみで、サブエージェントには入りません。失敗しても常に exit 0 で、セッションは止めません。

- 委譲ポリシーの正本は `session_context.py` の `POLICY` です。委譲ルールを変えるときはここを直し、この README の委譲フローも合わせます。
- エージェントを追加したら `POLICY` にフルネームで記載します（`hooks/test_session_context.py` が `agents/` の全エージェントの記載を検査します）。
- プラグインを有効にしている限り、メイン会話のモデルに関係なく注入されます。プロジェクト単位で止めたい場合は、そのプロジェクトの `.claude/settings.json` の `enabledPlugins` で無効にしてください。

```
plugins/model-routing/
├── .claude-plugin/plugin.json
├── agents/                       # coder / explorer / reviewer / advisor
└── hooks/
    ├── hooks.json                # SessionStart → session_context.py
    ├── session_context.py        # 委譲ポリシーの additionalContext 注入（ポリシーの正本）
    └── test_session_context.py
```
