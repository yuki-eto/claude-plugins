---
name: marp-slide-design
description: Marp（Markdown スライド）で発表スライドを作る・直すときの指針。情報デザインの原則（視線の流れ、整列と余白、ノイズの排除、フォントサイズと書体、3 色の配色とカラーユニバーサルデザイン、グラフと表の見せ方、1 枚の情報量）を Marp のテーマ CSS・ディレクティブ・Markdown 記法に落とし込む。Marp のデッキを新規作成するとき、スライドの内容・レイアウト・配色・グラフを決めるとき、既存デッキを見直すときに使う。
---

# Marp Slide Design

「伝えたいことを、伝えたい相手に、ちゃんと伝える」ためのスライドを Marp で作る指針。原則は天野由貴「情報デザインを意識したスライド作成入門 第3版」（広島大学, 2024）に基づく（[references/design-principles.md](references/design-principles.md) の出典を参照）。

## 前提

- Marp（Marp CLI または VS Code の Marp 拡張）で、Markdown からスライドを作る
- スライドは 16:9、1280×720px（Marp の既定）。PowerPoint の 28pt は約 37px に当たる
- 書体は BIZ UDPGothic（Windows 10 以降、macOS Sonoma 以降で標準搭載）を第一候補にする

## 3 つの目標

スライド 1 枚を表示している時間は約 1 分しかない。聴衆に考えさせずに伝わる状態を目指す。

1. **ぱっと見てわかる** — 視線が上→下、左→右に自然に流れる。文字が大きい
2. **整理されている** — 本当に伝えたいことだけを載せ、ノイズを削る
3. **ポイントが目立つ** — 強調は 1 箇所に絞り、アクセントカラーで示す

## 使い方

作業内容に合う章だけを読む。

| 章 | いつ読むか |
|----|-----------|
| [references/design-principles.md](references/design-principles.md) | スライドの構成・レイアウト・配色を決めるとき。原則の理由を知りたいとき |
| [references/marp-implementation.md](references/marp-implementation.md) | テーマ CSS、ディレクティブ、クラスの使い分け、ビルドと確認のコマンド |
| [references/charts-tables.md](references/charts-tables.md) | グラフの種類を選ぶとき、グラフ画像や表を作るとき |
| [references/review-checklist.md](references/review-checklist.md) | デッキを書き終えたとき、既存デッキを見直すとき |
| [templates/](templates/) | `theme.css`（テーマ `info-design`）と `deck.md`（雛形） |

## 作業の流れ

1. **伝えたいことを先に決める**。デッキ全体の結論を 1〜3 行で書き、それを最後のまとめスライドにする
2. **1 スライド 1 メッセージで構成を組む**。見出しだけを並べて流れを確認してから本文を書く
3. **雛形から書き始める**。`templates/theme.css` と `templates/deck.md` をコピーする（新規なら `/marp-new-deck` コマンド）
4. **本文を書く**。箇条書きは 1 枚 5 項目・各 1 行程度まで。収まらなければスライドを分ける（枚数が増えても話す時間はほとんど変わらない）
5. **図とグラフを入れる**。グラフは [references/charts-tables.md](references/charts-tables.md) に従って 2D・装飾なしで作り、強調したい系列だけアクセントカラーにする
6. **確認する**。`scripts/lint_deck.py` で機械的にわかる違反を検出し、PNG に書き出して目で確認する（`/marp-review` コマンド）

## 守ること（要約）

- 文章は左揃え。中央揃えにしない
- 本文は 37px（28pt）以上。行間は 1.3 程度
- 色は有彩色 3 色まで（ベース 7 割、メイン 2 割、アクセント 1 割）。赤と緑、ピンクと緑のように見分けにくい組み合わせで意味を区別しない
- 塗りと枠線を同時に使わない。影・グラデーション・3D は使わない
- 大学や会社のロゴは表紙だけに置く。内容と関係のないイラストは入れない
- 図を大きく見せたいときはスライドタイトルを省いてよい
- 最後は「ご清聴ありがとうございました」ではなく、まとめスライドにする（質疑応答中に表示しておける）
