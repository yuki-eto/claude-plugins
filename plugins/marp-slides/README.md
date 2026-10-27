# marp-slides

情報デザインの原則に沿って、Marp で「ぱっと見てわかる」スライドを作るためのプラグイン。

原則は天野由貴「情報デザインを意識したスライド作成入門 第3版」（広島大学, 2024, CC BY-SA 4.0）に基づく。<https://home.riise.hiroshima-u.ac.jp/~ten/slide_20240328.pdf>

## 収録物

| 種類 | 名前 | 内容 |
|------|------|------|
| skill | `marp-slide-design` | 原則（視線・配置・フォント・色・グラフ・構成）、Marp での実現方法、レビューチェックリスト |
| テンプレート | `skills/marp-slide-design/templates/` | テーマ `info-design`（`theme.css`）、`deck.md`、`.marprc.yml`、グラフの見本 SVG |
| command | `/marp-new-deck <タイトル> [dir]` | 雛形から新しいデッキを作る |
| command | `/marp-review <deck.md> [theme.css]` | lint・内容・PNG の目視でデッキを見直し、指摘を一覧にする |
| script | `scripts/lint_deck.py` | 機械的にわかる違反を検出する |

## lint_deck.py

```bash
python3 scripts/lint_deck.py deck.md --theme theme.css [--max-lines 8] [--max-chars 200]
```

| ルール | 検出内容 |
|--------|---------|
| `too-many-lines` | 1 枚の本文の行数が多い |
| `too-many-chars` | 1 枚の本文の文字数が多い |
| `small-font` | CSS の `font-size` が 37px（28pt）未満（footer・ページ番号・単位などは除外） |
| `centered-text` | 文章の中央揃え |
| `thanks-slide` | 「ご清聴ありがとうございました」だけのスライド |
| `too-many-colors` | CSS の有彩色が 3 色を超える |
| `logo-repeated` | ロゴが 2 枚以上のスライド、または header / footer に出ている |

指摘があれば exit 1。

## 前提

- Marp CLI（`marp` または `npx @marp-team/marp-cli`）。PDF・PNG 出力には Chrome / Edge / Firefox が要る
- フォント BIZ UDPGothic（Windows 10 以降、macOS Sonoma 以降で標準搭載）
- Python 3.9 以上（lint）
