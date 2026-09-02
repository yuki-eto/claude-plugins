# yuki-eto/claude-plugins

[Claude Code](https://docs.claude.com/en/docs/claude-code/plugins) のプラグインマーケットプレイス `yuki-eto-plugins` です。

マーケットプレイスの定義は `.claude-plugin/marketplace.json`、各プラグインの実体は `plugins/<name>/` 以下にあります。

## 収録プラグイン

| プラグイン | 説明 |
| --- | --- |
| [`model-routing`](./plugins/model-routing) | Fable司令塔 + Opus/Sonnet モデル振り分け構成 |
| [`no-shell-edit`](./plugins/no-shell-edit) | Bash 経由のファイル書き換え（`sed -i` / リダイレクト / インライン python 等）を禁止し Edit / Write ツールへ誘導する |

## インストール

マーケットプレイスを登録します。

```bash
claude plugin marketplace add yuki-eto/claude-plugins
```

Claude Code のセッション内でプラグインをインストールします。

```
/plugin install model-routing@yuki-eto-plugins
/plugin install no-shell-edit@yuki-eto-plugins
```

## 委譲ポリシーのテンプレート

`model-routing` を使う場合、ワークリポジトリの `CLAUDE.md` に以下を貼り付けてください。

```markdown
## 委譲ポリシー

原則すべてのタスクを `work-lead` サブエージェント（Agent ツールの `subagent_type` にはフルネームの `model-routing:work-lead` を指定）に委譲する。

メイン会話が直接扱うのは、次の 2 つのみ:

- `work-lead` が複数回失敗した問題
- アーキテクチャ全体に関わる設計判断

ファイルや関数の所在特定、使用箇所の洗い出しなど機械的な探索・検索は、メイン会話からも `explorer` サブエージェント（`subagent_type` は `model-routing:explorer`）に直接委譲してよい。メイン会話が自分でコードベースを読み回らない。
```

## プロジェクト単位でのマーケットプレイス登録

チームで共有する場合は、プロジェクトの `.claude/settings.json` に `extraKnownMarketplaces` を設定しておくと、各自が `claude plugin marketplace add` を実行しなくても済みます。

```json
{
  "extraKnownMarketplaces": {
    "yuki-eto-plugins": {
      "source": { "source": "github", "repo": "yuki-eto/claude-plugins" }
    }
  }
}
```

## 検証

```bash
claude plugin validate .
claude plugin validate ./plugins/model-routing
claude plugin validate ./plugins/no-shell-edit
python3 -m unittest discover -s plugins/no-shell-edit/hooks -p 'test_*.py'
```
