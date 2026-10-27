---
description: Marp のスライドデッキを情報デザインの原則で見直し、指摘を一覧にする
argument-hint: <deck.md> [theme.css]
---

# Marp デッキのレビュー

引数: `$ARGUMENTS`

`marp-slide-design` skill の原則で、既存のデッキを見直す。まず `marp-slide-design` skill の SKILL.md と `references/review-checklist.md` を読んでから始める。必要に応じて `references/design-principles.md`・`references/charts-tables.md` を引く。

このコマンドは指摘を出すところまで。デッキの修正は、ユーザーが指摘を確認して依頼したときに行う。

## 0. 引数の確認

- 第 1 引数 `<deck.md>` はレビュー対象。無ければユーザーに聞く
- 第 2 引数 `[theme.css]` はテーマ CSS。省略時は、front matter の `theme` と同じディレクトリの `.marprc.yml` の `themeSet` から探す。見つからなければ CSS の検査は deck.md 内の `<style>` だけにする

## 1. 機械的な検査

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lint_deck.py" <deck.md> --theme <theme.css>
```

`${CLAUDE_PLUGIN_ROOT}` が展開されていなければ、`~/.claude/plugins/` 配下で `marp-slides` プラグインの `scripts/lint_deck.py` を探す。閾値（`--max-lines 8`、`--max-chars 200`）は目安なので、指摘はそのまま採用せず、スライドの内容を見て判断する。

## 2. 内容の検査

deck.md を読み、チェックリストの「全体の構成」「1 枚の情報量」「グラフと表」「著作権」の項目を確認する。見出しだけを順に抜き出して、話の流れが通るかも確認する。

## 3. 目視の検査

デッキのディレクトリで PNG に書き出し、各スライドを Read で開いて、チェックリストの「目視」の項目を確認する。

```bash
marp <deck.md> --images png -o <scratchpad>/review/slide.png
```

出力先はスクラッチパッドにして、ユーザーのリポジトリに残さない。ブラウザが起動できず失敗した場合は、サンドボックス外での実行をユーザーに確認する。それも難しければ、目視の項目は未確認として報告する。

## 4. 報告

スライドごとに指摘をまとめる。各指摘には次を書く。

- スライド番号（と deck.md の行番号）
- どの原則に反しているか（チェックリストの項目）
- 具体的な直し方（分割する、`figure` クラスにする、アクセントを 1 箇所に絞る、など）

深刻度順（伝わらない・誤解を招く → 読みにくい → 細かな体裁）に並べる。確認できなかった項目があれば、その旨も書く。
