---
description: Marp の新規スライドデッキを marp-slide-design の雛形（テーマ info-design）で作成する
argument-hint: <タイトル> [target-dir]
---

# Marp デッキの新規作成

引数: `$ARGUMENTS`

`marp-slide-design` skill の雛形で、新しいスライドデッキを作る。まず `marp-slide-design` skill の SKILL.md と `references/marp-implementation.md` を読んでから始める。

雛形は、このプラグインの `skills/marp-slide-design/templates/` にある（`${CLAUDE_PLUGIN_ROOT}/skills/marp-slide-design/templates/`。変数が展開されていなければ `~/.claude/plugins/` 配下で `marp-slides` プラグインのディレクトリを探す）。

## 0. 引数と前提の確認

- 第 1 引数 `<タイトル>` は表紙に入れる発表タイトル。無ければユーザーに聞く
- 第 2 引数 `[target-dir]` はデッキを置くディレクトリ。省略したら `./slides`
- `<target-dir>/deck.md` が既にあれば上書きせず、止めてユーザーに報告する
- 次をユーザーに確認する（分からなければ既定値で進め、あとで変えられると伝える）
  - 発表者名・所属
  - 縦横比（既定 16:9。会場のプロジェクタが 4:3 なら 4:3）
  - 配色を変えたいか（既定はベース #F4F1EA、メイン #1F3A5F、アクセント #D9730D）
  - 発表時間と、伝えたい結論（構成を組むのに使う）

## 1. 雛形のコピー

Read で雛形を読み、Write で `<target-dir>` に書き出す（シェルのコピーやリダイレクトは使わない）。

- `templates/theme.css` → `<target-dir>/theme.css`
- `templates/.marprc.yml` → `<target-dir>/.marprc.yml`
- `templates/deck.md` → `<target-dir>/deck.md`
- `templates/images/chart.svg` → `<target-dir>/images/chart.svg`（図スライドの見本。不要なら図スライドごと消す）

## 2. 置換と構成

- 表紙の「発表タイトル」「発表者名 ／ 所属」を置き換える
- 縦横比が 4:3 なら front matter の `size` を変える
- 配色を変えるなら `theme.css` の `--color-base` / `--color-main` / `--color-accent` を変える。有彩色は 3 色だけにする
- ユーザーから結論と発表時間を聞けていれば、1 枚 1 分を目安に見出しだけの骨組みを作り、最後の `summary` スライドに結論を書く。本文はユーザーと相談しながら埋める

## 3. 確認

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lint_deck.py" <target-dir>/deck.md --theme <target-dir>/theme.css
```

指摘があれば直す。続けて `<target-dir>` で `marp deck.md --images png -o out/slide.png` を実行し、PNG を Read で開いて表示を確認する（ブラウザが起動できず失敗した場合は、サンドボックス外での実行をユーザーに確認する）。

## 4. 報告

作ったファイル、プレビューやビルドのコマンド（`marp -s .`、`marp deck.md --pdf`）、VS Code でプレビューする場合の設定（`references/marp-implementation.md` の「ファイル構成」）を伝える。
