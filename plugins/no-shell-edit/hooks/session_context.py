#!/usr/bin/env python3
"""no-shell-edit: SessionStart hook.

セッション開始（startup / resume / clear / compact）時に、ファイル変更のポリシーを
additionalContext として注入し、モデルが最初から Edit / Write ツールを使うようにする。
失敗しても常に exit 0（fail-open）。
"""

import json
import sys

POLICY = """\
[no-shell-edit] ファイルの作成・変更は Edit / Write ツールのみで行う。Bash をエディタ代わりに使わない。
- deny される例: 単一ファイルへの `sed -i` / `perl -i`、`> file` `>> file` のリダイレクト、`tee file`、`python3 -c` / `node -e` / heredoc スクリプトからのファイル書き込み、`bash -c` 経由の同等操作。
- 許可される例外: 複数ファイルへの一括置換（`sed -i ... a.py b.py`、glob、`find -exec`、`xargs`、`for` ループ内）。`patch` / `git apply` はユーザー確認（ask）になる。
- 一時的な出力は /tmp または $TMPDIR 配下に書き出す（そこへのリダイレクトは許可される）。"""


def main() -> int:
    try:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": POLICY,
                    }
                },
                ensure_ascii=False,
            )
        )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
