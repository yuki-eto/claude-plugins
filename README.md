# yuki-eto/claude-plugins

[Claude Code](https://docs.claude.com/en/docs/claude-code/plugins) のプラグインマーケットプレイス `yuki-eto-plugins` です。

マーケットプレイスの定義は `.claude-plugin/marketplace.json`、各プラグインの実体は `plugins/<name>/` 以下にあります。

## 収録プラグイン

| プラグイン | 説明 |
| --- | --- |
| [`model-routing`](./plugins/model-routing) | Opus 司令塔 + Fable エスカレーションのモデル振り分け構成 |
| [`no-shell-edit`](./plugins/no-shell-edit) | Bash 経由のファイル書き換え（`sed -i` / リダイレクト / インライン python 等）を禁止し Edit / Write ツールへ誘導する |
| [`godot-csharp`](./plugins/godot-csharp) | Godot 4.x (.NET/C#) で iOS/macOS 向けゲームを作るための指針 skill・新規プロジェクト作成コマンド（`/godot-new-project`）・サンドボックス用 dotnet フラグ警告 hook |
| [`tech-notes`](./plugins/tech-notes) | 作業中に得た技術的な知見を匿名化して個人用ノートリポジトリ `~/tech-notes` に記録する skill（`/note`） |

## インストール

マーケットプレイスを登録します。

```bash
claude plugin marketplace add yuki-eto/claude-plugins
```

Claude Code のセッション内でプラグインをインストールします。

```
/plugin install model-routing@yuki-eto-plugins
/plugin install no-shell-edit@yuki-eto-plugins
/plugin install godot-csharp@yuki-eto-plugins
/plugin install tech-notes@yuki-eto-plugins
```

## model-routing の委譲ポリシー

`model-routing` の委譲ポリシーは、プラグインの SessionStart フックがセッション開始時に自動で注入します。ワークリポジトリの `CLAUDE.md` への記載は不要です。メイン会話のモデルは Opus（`/model` で設定）で動かす前提です。詳細は [`plugins/model-routing/README.md`](./plugins/model-routing/README.md) を参照してください。

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
claude plugin validate ./plugins/godot-csharp
claude plugin validate ./plugins/tech-notes
python3 -m unittest discover -s plugins/model-routing/hooks -p 'test_*.py'
python3 -m unittest discover -s plugins/no-shell-edit/hooks -p 'test_*.py'
python3 -m unittest discover -s plugins/godot-csharp/hooks -p 'test_*.py'
```
