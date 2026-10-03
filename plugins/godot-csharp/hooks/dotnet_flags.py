#!/usr/bin/env python3
"""godot-csharp: PreToolUse hook for the Bash tool.

Godot プロジェクトで `dotnet build` / `dotnet test` に、サンドボックス内で MSBuild の
ノード間 IPC が遮断される問題の回避フラグ（-m:1 -nodeReuse:false --disable-build-servers）
が欠けていたら、エージェントに警告（additionalContext）を渡す。
`dotnet test` に --no-build が無い場合も警告する（テストはサンドボックスを外して実行するため、
付けないとビルドと NuGet の restore までサンドボックスの外で走る）。

- deny / ask はしない。コマンドは常にそのまま実行される。
- 判定は決定的。標準ライブラリのみ。
- 解析に失敗した場合も何も出力せず exit 0。

出力形式:
  {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                          "additionalContext": "..."}}
"""

from __future__ import annotations

import glob
import json
import os
import re
import shlex
import sys
from typing import Optional

REQUIRED_FLAGS = (
    ("-m:1", re.compile(r"^(?:--?|/)(?:m|maxcpucount):1$", re.IGNORECASE)),
    ("-nodeReuse:false", re.compile(r"^(?:--?|/)(?:nodereuse|nr):false$", re.IGNORECASE)),
    ("--disable-build-servers", re.compile(r"^--disable-build-servers$", re.IGNORECASE)),
)
TARGET_SUBCOMMANDS = ("build", "test")
WRAPPERS = {"env", "time", "command", "exec", "nohup", "sudo", "nice"}
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def is_godot_project(directory: Optional[str]) -> bool:
    if not directory or not os.path.isdir(directory):
        return False
    if os.path.isfile(os.path.join(directory, "project.godot")):
        return True
    pattern = os.path.join(glob.escape(directory), "*", "project.godot")
    return bool(glob.glob(pattern))


def split_segments(command: str) -> list:
    """`&&` `||` `;` `|` `&` 改行で分割する（クォート内は分割しない）。"""
    command = command.replace("\\\n", " ")
    segments = []
    buf = []
    i = 0
    n = len(command)
    quote = None
    while i < n:
        c = command[i]
        if quote == "'":
            buf.append(c)
            if c == "'":
                quote = None
        elif quote == '"':
            buf.append(c)
            if c == "\\" and i + 1 < n:
                i += 1
                buf.append(command[i])
            elif c == '"':
                quote = None
        elif c == "\\" and i + 1 < n:
            buf.append(c)
            i += 1
            buf.append(command[i])
        elif c in "'\"":
            quote = c
            buf.append(c)
        elif c in ";|\n":
            segments.append("".join(buf))
            buf = []
        elif c == "&":
            prev = command[i - 1] if i > 0 else ""
            nxt = command[i + 1] if i + 1 < n else ""
            if prev in ("<", ">") or nxt == ">":
                buf.append(c)
            else:
                segments.append("".join(buf))
                buf = []
        else:
            buf.append(c)
        i += 1
    segments.append("".join(buf))
    return [s for s in segments if s.strip()]


def dotnet_args(segment: str) -> Optional[tuple]:
    """セグメントが dotnet build/test を呼んでいれば (subcommand, 以降のトークン) を返す。"""
    try:
        tokens = shlex.split(segment, comments=False)
    except ValueError:
        return None
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx].lstrip("({")
        if not tok:
            idx += 1
            continue
        if ASSIGNMENT_RE.match(tok) or tok in WRAPPERS:
            idx += 1
            continue
        if tok.startswith("-") and idx > 0 and tokens[idx - 1].lstrip("({") in WRAPPERS:
            idx += 1
            continue
        break
    if idx >= len(tokens):
        return None
    if os.path.basename(tokens[idx].lstrip("({")) != "dotnet":
        return None
    rest = tokens[idx + 1:]
    for pos, tok in enumerate(rest):
        if tok.startswith("-"):
            continue
        if tok in TARGET_SUBCOMMANDS:
            return tok, rest[pos + 1:]
        return None
    return None


def missing_flags(args: list) -> list:
    return [name for name, pattern in REQUIRED_FLAGS if not any(pattern.match(a) for a in args)]


def build_warning(subcommand: str, missing: list, no_build_missing: bool) -> str:
    msg = ""
    if missing:
        msg += (
            f"`dotnet {subcommand}` に {' '.join(missing)} が付いていません。"
            "サンドボックス内では MSBuild のノード間 IPC が遮断され、5 分固まった後に"
            "「0 エラー」で失敗します。"
        )
    if no_build_missing:
        msg += (
            "`dotnet test` に --no-build が付いていません。"
            "テストはサンドボックスを外して実行するため、付けないとビルドと NuGet の restore まで"
            "サンドボックスの外で走ります。先にサンドボックス内で `dotnet build` を通してください。"
        )
    if subcommand == "test":
        msg += "推奨形: `dotnet test <csproj> -m:1 -nodeReuse:false --disable-build-servers --no-build`"
        msg += (
            " vstest はループバック TCP を使うため、テストはサンドボックスを外して実行する必要があります。"
            "外すのはこのコマンドだけにし、`&&` などで他のコマンドと連結しないでください。"
        )
    else:
        msg += "推奨形: `dotnet build <sln> -m:1 -nodeReuse:false --disable-build-servers`"
    return msg


def evaluate(command: str) -> Optional[str]:
    warnings = []
    for segment in split_segments(command):
        found = dotnet_args(segment)
        if found is None:
            continue
        subcommand, args = found
        missing = missing_flags(args)
        no_build_missing = subcommand == "test" and not any(a.lower() == "--no-build" for a in args)
        if missing or no_build_missing:
            warnings.append(build_warning(subcommand, missing, no_build_missing))
    return "\n".join(warnings) if warnings else None


def main() -> int:
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            return 0
        tool_input = data.get("tool_input")
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        if not isinstance(command, str) or not command.strip():
            return 0
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd")
        if not is_godot_project(project_dir):
            return 0
        warning = evaluate(command)
        if warning:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "additionalContext": warning,
                        }
                    },
                    ensure_ascii=False,
                )
            )
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
