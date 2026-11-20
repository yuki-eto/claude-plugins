# session-title

セッション名の先頭に `[リポジトリ名]` を付けるプラグイン。サイドバーや `/resume` の一覧で、どのリポジトリのセッションかを見分けやすくします。

## 付け方

プロンプトを送るたびに UserPromptSubmit フックが動き、`hookSpecificOutput.sessionTitle` でセッション名を設定します。

| 状況 | 接頭辞 |
| --- | --- |
| Git リポジトリ内 | `[リポジトリ名]`。worktree 内でも本体のリポジトリ名（`git rev-parse --git-common-dir` から取得） |
| Git リポジトリ外 | `[global]` |
| Desktop アプリでフォルダ未選択（cwd が `.../scratch-workspaces/...`） | `[global]` |

| 現在のセッション名 | 結果 |
| --- | --- |
| まだ名前がない（最初のプロンプト） | `[接頭辞] プロンプトの先頭行（40 文字まで）` |
| 接頭辞なし（`/rename` した後など） | `[接頭辞] 現在の名前` |
| 別の `[...]` で始まる（セッションのフォルダを移動した後など） | 先頭の `[...]` を正しい接頭辞に置き換える |
| すでに正しい接頭辞で始まる | 変更しない |

## 制約

- 最初のプロンプトで名前を設定するので、Claude Code が自動生成する要約タイトルは使われません。代わりにプロンプトの先頭行が入ります。
- 自動生成タイトルはフックの入力（`session_title`）に含まれないため、後から付け直すことはできません。
- 手動でリネームした場合、接頭辞が付き直るのは次にプロンプトを送ったときです。
- 先頭が `[...]` の名前（例: `[WIP] 認証`）は、その部分が接頭辞に置き換わります。

## 無効化

環境変数 `SESSION_TITLE_DISABLE=1` を設定すると、フックは何もしません。

## ファイル構成

```
plugins/session-title/
├── .claude-plugin/plugin.json
├── hooks/
│   ├── hooks.json             # UserPromptSubmit → title_prefix.py
│   ├── title_prefix.py        # 本体（python3 標準ライブラリのみ、fail-open）
│   └── test_title_prefix.py
└── README.md
```

## テスト

```bash
python3 -m unittest discover -s plugins/session-title/hooks -p 'test_*.py'
```

フック単体を手で試す場合:

```bash
echo '{"cwd":"'"$PWD"'","prompt":"ログインを直して"}' | python3 plugins/session-title/hooks/title_prefix.py
```

## インストール

```bash
claude plugin marketplace add yuki-eto/claude-plugins
```

```
/plugin install session-title@yuki-eto-plugins
```
