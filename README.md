# yuki-eto/claude-plugins

[Claude Code](https://docs.claude.com/en/docs/claude-code/plugins) のプラグインマーケットプレイス `yuki-eto-plugins` です。

マーケットプレイスの定義は `.claude-plugin/marketplace.json`、各プラグインの実体は `plugins/<name>/` 以下にあります。

## 収録プラグイン

| プラグイン | 説明 |
| --- | --- |
| [`model-routing`](./plugins/model-routing) | Opus 司令塔 + Fable エスカレーションのモデル振り分け構成 |
| [`no-shell-edit`](./plugins/no-shell-edit) | Bash 経由のファイル書き換え（`sed -i` / リダイレクト / インライン python 等）を禁止し Edit / Write ツールへ誘導する |
| [`godot-csharp`](./plugins/godot-csharp) | Godot 4.x (.NET/C#) で iOS/macOS 向けゲームを作るための指針 skill・新規プロジェクト作成コマンド（`/godot-new-project`）・サンドボックス用 dotnet フラグ警告 hook |

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
```

## 委譲ポリシーのテンプレート

`model-routing` を使う場合、ワークリポジトリの `CLAUDE.md` に以下を貼り付けてください。メイン会話のモデルは Opus（`/model` で設定）で動かす前提です。

```markdown
## 委譲ポリシー

メイン会話（Opus）は計画・設計判断・成果物の検証を担い、実作業は下位のサブエージェントに委譲する。

- 仕様が明確な実装・単純な修正は `coder`（Agent ツールの `subagent_type` にはフルネームの `model-routing:coder` を指定）に委譲する。委譲時は対象ファイル・期待する変更・完了条件を具体的に伝え、戻ってきた成果物は必ず自分で検証する（差分確認・テスト実行）。仕様が曖昧な部分は `coder` に投げず、メイン会話で判断する。
- ファイルや関数の所在特定、使用箇所の洗い出しなど機械的な探索は `explorer`（`model-routing:explorer`）に委譲する。メイン会話が自分でコードベースを広く読み回らない。探索結果（パス・行番号）を `coder` に渡す場合はそのまま引き継ぎ、二重に探索させない。
- 次のいずれかに当てはまったら `advisor`（`model-routing:advisor`、Fable）にエスカレーションする。呼ぶ際は問題・試したこと・失敗内容・関連パスを渡す。`advisor` の返した方針をもとに、実装は `coder` に委譲する。
  - 同じ問題で修正→検証が 2 回失敗した
  - 仮説が尽きて原因を特定できない
  - アーキテクチャ全体に関わる設計判断

サブエージェントの出力はユーザーに直接見えないため、メイン会話が要約してユーザーに報告する。
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
claude plugin validate ./plugins/godot-csharp
python3 -m unittest discover -s plugins/no-shell-edit/hooks -p 'test_*.py'
python3 -m unittest discover -s plugins/godot-csharp/hooks -p 'test_*.py'
```
