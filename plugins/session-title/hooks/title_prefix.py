#!/usr/bin/env python3
"""session-title: UserPromptSubmit hook.

セッション名の先頭に `[リポジトリ名]`（リポジトリ外・フォルダ未選択なら `[global]`）を付ける。
失敗しても常に exit 0（fail-open）。
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

GLOBAL = "global"
MAX_PROMPT_CHARS = 40
LEADING_TAG = re.compile(r"^\[[^\]]*\]\s*")


def repo_name(cwd: str) -> str:
    if not cwd or "/scratch-workspaces/" in cwd:
        return GLOBAL
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return GLOBAL
    if result.returncode != 0 or not result.stdout.strip():
        return GLOBAL
    # worktree でも本体リポジトリの名前を返すため、--show-toplevel ではなく共通 git ディレクトリから引く
    common = Path(result.stdout.strip())
    if common.name == ".git":
        return common.parent.name or GLOBAL
    return common.name.removesuffix(".git") or GLOBAL


def summarize(prompt: str) -> str:
    for line in prompt.splitlines():
        line = " ".join(line.split())
        if line:
            if len(line) > MAX_PROMPT_CHARS:
                return line[:MAX_PROMPT_CHARS] + "…"
            return line
    return ""


def build_title(prefix: str, current: str, prompt: str) -> str | None:
    tag = f"[{prefix}]"
    if current:
        if current == tag or current.startswith(tag + " "):
            return None
        rest = LEADING_TAG.sub("", current, count=1)
    else:
        rest = summarize(prompt)
    return f"{tag} {rest}".rstrip()


def main() -> int:
    if os.environ.get("SESSION_TITLE_DISABLE") == "1":
        return 0
    try:
        data = json.load(sys.stdin)
        title = build_title(
            repo_name(data.get("cwd") or ""),
            (data.get("session_title") or "").strip(),
            data.get("prompt") or "",
        )
        if title is None:
            return 0
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "sessionTitle": title,
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
