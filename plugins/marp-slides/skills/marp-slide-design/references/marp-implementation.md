# Marp での実現方法

[design-principles.md](design-principles.md) の原則を、Marp のテーマ CSS・ディレクティブ・Markdown 記法に置き換える方法。テーマは `templates/theme.css`（`info-design`）を前提にする。

## ファイル構成

```
slides/
  deck.md          … スライド本体
  theme.css        … templates/theme.css のコピー（配色はここで変える）
  .marprc.yml      … templates/.marprc.yml のコピー（Marp CLI の設定）
  images/          … 図・グラフ・写真
```

`.marprc.yml` では次を有効にしている。

- `themeSet: ./theme.css` … `theme: info-design` を解決するため
- `html: true` … `<span class="unit">` や `<div class="columns">` を使うため（Marp は既定で HTML のほとんどを無効にしている）
- `allowLocalFiles: true` … PDF・PNG 出力でローカル画像を読むため

VS Code の Marp 拡張でプレビューするときは、`.vscode/settings.json` に次を書く。

```json
{
  "markdown.marp.themes": ["./slides/theme.css"],
  "markdown.marp.enableHtml": true
}
```

## サイズと文字の大きさ

- 16:9 は 1280×720px、4:3 は 960×720px。どちらも PowerPoint の 28pt ≒ **37px** になる
- テーマの本文は 40px、h1 は 52px。本文を 37px 未満に下げない
- 会場が広い・スクリーンが小さいときは、`<style>` で `section { font-size: 44px; }` のように**上げる**方向にだけ調整する
- 縦横比は front matter の `size: 16:9` / `size: 4:3` で切り替える（テーマに両方を定義済み）。会場のプロジェクタに合わせる

## front matter

```yaml
---
marp: true
theme: info-design
paginate: true
---
```

- `paginate` はページ番号が質疑で役立つなら付ける。不要ならノイズなので外す
- `header` / `footer` に所属名やロゴを入れない。全ページに出るのでノイズになる。必要なら表紙だけに書く

## クラスの使い分け

ディレクティブ `<!-- _class: xxx -->`（先頭の `_` はそのスライドだけに適用する意味）で切り替える。

| クラス | 用途 | 書き方 |
|--------|------|--------|
| （なし） | 通常のスライド。h1 をタイトルにして本文を上から並べる | `# タイトル` + 箇条書き |
| `title` | 表紙。タイトル・発表者・所属。ロゴを置くならここだけ | `<!-- _class: title -->` |
| `figure` | タイトルを省いて図を大きく見せる | `<!-- _class: figure -->` + `![](images/x.svg)` |
| `summary` | 最後のまとめ。質疑応答中も表示しておく | `<!-- _class: summary -->` |

表紙・まとめでページ番号を消すときは `<!-- _paginate: false -->` を併記する。

## 原則ごとの書き方

### 視線の流れ・揃え

- テーマは `text-align: left`、上詰め（`justify-content: flex-start`）にしてある。`<center>` や `text-align: center` を足さない
- 手順やフローは左から右に並べる。2 列にするときは `columns` を使い、左に図・右に説明、または左に前・右に後の順にする

```markdown
<div class="columns">
<div>

![](images/before.svg)

</div>
<div>

- 説明 1
- 説明 2

</div>
</div>
```

Markdown を HTML ブロックの中で使うときは、タグと Markdown の間に空行を入れる。

### 余白

- テーマの padding（上下 56px・左右 80px）を狭めない。文字を詰め込みたくなったらスライドを分ける
- 画像はサイズ指定で余白を残す。`![w:900](images/x.svg)`、高さで揃えるなら `![h:480](...)`
- 背景画像を半分に置くなら `![bg right:40% contain](images/x.png)`。本文と画像の間に余白が確保される

### 強調

- 文中の強調は `**太字**`（テーマでアクセントカラー + 太字になる）。1 枚に 1〜2 箇所まで
- 段落や項目をまとめて目立たせるなら `<div class="box">`（ベースカラーの塗りだけ。枠線は付けない）
- 単位を小さくする: `120<span class="unit">万人</span>`
- 1 つの数値を主役にするなら `<span class="stat">120</span><span class="unit">万人</span>`（数値を 2.4 倍・アクセントカラーにする）
- 斜体（`*text*`）は和文が読みにくいので、テーマでは斜体にせず、メインカラーの太字にしている

### ノイズを避ける

- ロゴは表紙だけ: `<!-- _class: title -->` のスライドに `<img class="logo" src="images/logo.svg" alt="logo">`
- 飾りの画像・アイコンを空白埋めに入れない
- 背景画像に模様や写真を敷かない（文字のコントラストが落ちる）

### 配色

テーマの CSS 変数を書き換えて配色を決める。有彩色はこの 3 つだけにし、他は白・黒・グレーにする。

```css
section {
  --color-base: #F4F1EA;   /* ベース: 明度高・彩度低。ボックスの塗り */
  --color-main: #1F3A5F;   /* メイン: 明度低。見出し */
  --color-accent: #D9730D; /* アクセント: メインと反対の色相。強調 */
}
```

- デッキ固有の変更は `theme.css` を直接直すか、`deck.md` の `<style>` で変数を上書きする
- グラフ画像の色も同じ 3 色＋グレーに揃える（[charts-tables.md](charts-tables.md)）
- 赤と緑など見分けにくい組み合わせで意味を区別しない。色以外にラベル・形でも区別する

### 1 枚の情報量

- 目安: 見出し 1 つ + 箇条書き 5 項目以内、各項目は 1 行で収まる長さ、本文 200 字以内
- 長い説明は発表者ノート（ディレクティブ以外の HTML コメント `<!-- ここに話す内容 -->`）に移す。スライドに書いて読み上げない
- 図を大きく見せたいスライドは `figure` クラスにしてタイトルを省く

## ビルドと確認

```bash
marp deck.md --pdf                 # PDF（配布・発表用）
marp deck.md --pptx                # PowerPoint
marp deck.md --images png          # 1 枚ずつ PNG（目視確認用）
marp -s .                          # ブラウザでプレビュー（ファイル変更を自動反映）
```

`.marprc.yml` があるディレクトリで実行する。`marp` が無ければ `npx @marp-team/marp-cli@latest` で代用する。

PDF・PNG・PPTX の出力にはローカルの Chrome / Edge / Firefox が要る。Claude Code のサンドボックス内ではブラウザが起動できず失敗することがある。その場合はサンドボックス外での実行をユーザーに確認する。

### エージェントによる目視確認

1. `marp deck.md --images png -o out/slide.png` で PNG に書き出す（`out/slide.001.png` のように連番になる）
2. 各 PNG を Read で開き、[review-checklist.md](review-checklist.md) の「目視」の項目を確認する
3. `python3 <plugin>/scripts/lint_deck.py deck.md --theme theme.css` で機械的な違反を確認する

## 落とし穴

- **HTML が表示されない**: `html: true`（`.marprc.yml`）または `--html` が無いと、`<span>` や `<div>` は無視される
- **テーマが見つからない**: `theme: info-design` は `themeSet` か `--theme-set theme.css` で CSS を渡さないと解決できず、既定テーマで描画される
- **画像が PDF に出ない**: `allowLocalFiles: true`（または `--allow-local-files`）が無いと、ローカル画像が読み込まれない
- **フォントが変わる**: BIZ UDPGothic が入っていない環境では代替フォントで描画され、行の折り返しが変わる。PDF は BIZ UDPGothic のある環境で作る
- **`---` でスライドが切れる**: 本文中の水平線のつもりの `---` もスライド区切りになる。区切り線が必要なら `<hr>` を使う
