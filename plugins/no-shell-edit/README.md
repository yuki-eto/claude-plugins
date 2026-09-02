# no-shell-edit

Bash をテキストエディタ代わりに使うコマンドを検知して止め、Edit / Write ツールへ誘導するプラグイン。

Claude はコードやドキュメントを修正するとき、Edit / Write ではなく `sed -i` や `>` リダイレクト、`python3 -c` でのファイル書き込みを使うことがあります。このプラグインは Bash ツールの PreToolUse フックでコマンド文字列を解析し、そうした操作を `deny` して理由（どのツールを使うべきか）をモデルに返します。判定は決定的で、LLM は使いません。

## 判定ルール

| 判定 | 対象 | 例 |
| --- | --- | --- |
| deny | 単一ファイルへの in-place 置換 | `sed -i 's/a/b/' file.py`、`perl -pi -e ... file`、`ruby -pi -e ... file`、`gawk -i inplace ... file` |
| deny | ファイルへのリダイレクト（stdout） | `echo x > out.txt`、`printf ... >> src/a.py`、`cat > f <<EOF`、`cmd &> out.log` |
| deny | ファイルへ書くコマンド | `tee out.txt`、`dd of=img.bin`、`truncate -s 0 file` |
| deny | インラインスクリプトからのファイル書き込み | `python3 -c "open('f','w')..."`、`python3 - <<EOF ... write_text ...`、`node -e "fs.writeFileSync(...)"`、`ruby -e 'File.write(...)'`、`php -r 'file_put_contents(...)'` |
| deny | 上記をシェル経由で隠したもの | `bash -c "echo x > f"`、`eval '...'`、`xargs -I{} sh -c 'echo x > {}'`、`find ... -exec sh -c '...'`、`echo "$(echo x > y)"` |
| ask | 差分の適用 | `patch -p1 < fix.patch`、`git apply x.diff` |
| ask | 書き込み先が変数で判定できない | `cmd > "$OUT"`、`tee "$dest"` |

### 許可されるもの（判定を返さず、通常の許可フローへ）

- **複数ファイルへの一括置換**: `sed -i 's/a/b/' a.py b.py`、glob（`src/*.py`）、`$(git ls-files ...)`、`grep -rl foo . | xargs sed -i ...`、`find ... -exec sed -i ... {} +`、`for f in *.py; do sed -i ... "$f"; done`
- **一時ファイルへの出力**: `/tmp/`、`/private/tmp/`、`/var/tmp/`、`/var/folders/`、`$TMPDIR` 配下、`$(mktemp)`、`tmp` / `temp` / `scratch` を含む変数名（`> "$tmp"`）、`/dev/null` 等
- **stderr のリダイレクト**: `2>err.log`、`2>&1`
- **正規のツール実行**: `prettier --write`、`gofmt -w`、`eslint --fix`、`npm install`、`git commit`、`cargo fmt` など
- **読み取り系**: `sed 's/a/b/' file | head`、`sed -n '1,5p' file`、`perl -ne ...`、`python3 -c "print(open('f').read())"`、`python3 script.py`、`python3 -m pytest`
- **dry-run**: `patch --dry-run`、`git apply --check` / `--stat` / `--numstat` / `--summary`
- **Claude Code のコミットイディオム**: `git commit -m "$(cat <<'EOF' ... EOF)"`

### 対象外（既知の抜け道）

- `cp` / `mv` / `rm` / `curl -o`（ファイル管理は編集とみなさない）。`python3 -c ... > /tmp/x && mv /tmp/x file` のような迂回は検知しない。
- sed スクリプト内の `w file` コマンド、awk プログラム内の `> "file"` 出力。
- ログ出力のリダイレクト（`npm test > test.log`）も deny になる。`/tmp` か `$TMPDIR` 配下に書き出すこと。

## SessionStart での方針注入

セッション開始時（startup / resume / clear / compact）に、上記の方針を数行の `additionalContext` として注入します。モデルが最初から Edit / Write を選ぶようになり、deny → やり直しの往復を減らします。

## 無効化

環境変数 `NO_SHELL_EDIT_DISABLE=1` を設定すると、フックは何も判定せず通常の許可フローに任せます。

## ファイル構成

```
plugins/no-shell-edit/
├── .claude-plugin/plugin.json
├── hooks/
│   ├── hooks.json           # PreToolUse(Bash) → guard.py、SessionStart → session_context.py
│   ├── guard.py             # 判定本体（python3 標準ライブラリのみ、fail-open）
│   ├── session_context.py   # 方針の additionalContext 注入
│   └── test_guard.py        # テーブル駆動テスト
└── README.md
```

`guard.py` はコマンド文字列を自前のスキャナでトークン化し（heredoc 抽出 → クォート / `$(...)` を保持した単語分割 → `|` `;` `&&` 等で単純コマンドに分割）、各コマンドにルールを適用します。解析に失敗した場合は fail-open（何も出力せず exit 0）です。

## テスト

```bash
python3 -m unittest discover -s plugins/no-shell-edit/hooks -p 'test_*.py'
```

フック単体を手で試す場合:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"sed -i s/a/b/ x.txt"}}' | python3 plugins/no-shell-edit/hooks/guard.py
```

## インストール

```bash
claude plugin marketplace add yuki-eto/claude-plugins
```

```
/plugin install no-shell-edit@yuki-eto-plugins
```

ローカルで試す場合は `claude --plugin-dir ./plugins/no-shell-edit` で起動し、`/hooks` で登録を確認してください。
