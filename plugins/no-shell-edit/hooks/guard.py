#!/usr/bin/env python3
"""no-shell-edit: PreToolUse hook for the Bash tool.

Bash をテキストエディタ代わりに使うコマンド（単一ファイルへの sed -i、ファイルへの
リダイレクト、tee、インライン python / node からの書き込み など）を検知し、
Edit / Write ツールへ誘導する。

- 判定は決定的（LLM は使わない）。標準ライブラリのみ。
- 判定を出さない場合は何も出力せず exit 0 → 通常の許可フローへ。
- 解析に失敗した場合も fail-open（何も出力せず exit 0）。

出力形式:
  {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                          "permissionDecision": "deny" | "ask",
                          "permissionDecisionReason": "..."}}
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field, replace
from typing import Optional

MAX_DEPTH = 3
DISABLE_ENV = "NO_SHELL_EDIT_DISABLE"

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

ALLOWED_DEV = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty"}
ALLOWED_DEV_PREFIXES = ("/dev/fd/", "/proc/self/fd/")
TEMP_PREFIXES = (
    "/tmp/",
    "/private/tmp/",
    "/var/tmp/",
    "/var/folders/",
    "$TMPDIR",
    "${TMPDIR}",
)
TEMP_VAR_NAME_RE = re.compile(r"tmp|temp|scratch|out_?file", re.IGNORECASE)
VAR_REF_RE = re.compile(r"^\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# 先頭に付くラッパーコマンドと、値を取るフラグ
WRAPPERS = {
    "sudo": {"-u", "-g", "-C", "-h", "-p", "-U", "-r", "-t", "-D"},
    "doas": {"-u", "-C"},
    "env": {"-u", "-C", "-S"},
    "command": set(),
    "nohup": set(),
    "nice": {"-n"},
    "time": set(),
    "timeout": {"-k", "-s"},
    "builtin": set(),
    "exec": set(),
}
SHELL_KEYWORDS = {
    "if", "then", "else", "elif", "fi", "for", "in", "do", "done", "while",
    "until", "case", "esac", "{", "}", "!", "time", "select", "function",
}
LOOP_KEYWORDS = {"for", "while", "until"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "mksh"}
STDIN_PRODUCERS = {"echo", "printf", "cat"}

SEPARATOR_OPS = {"\n", ";", ";;", "&&", "||", "&", "(", ")", "<(", ">(", "|", "|&"}
PIPE_OPS = {"|", "|&"}
OPERATORS = sorted(
    ["<<<", "&>>", "&>", ">>", ">|", ">&", "<&", "|&", "&&", "||", ";;", "<(", ">(",
     "<<", "<", ">", "|", "&", ";", "(", ")", "\n"],
    key=len,
    reverse=True,
)
FD_REDIRECT_RE = re.compile(r"(\d+)(>>|>&|>|<&|<)")
REDIRECT_RE = re.compile(r"^(\d*)(&>>|&>|>>|>\||>&|>|<&|<<<|<<|<)$")
HEREDOC_RE = re.compile(r"(?<!<)<<(?!<)(-?)\s*(['\"\\]?)(\w+)['\"]?")

SED_INPLACE_RE = re.compile(r"^-[nErsuz]*[iI]")
PERL_INPLACE_RE = re.compile(r"^-[pnlaw0-9]*i")
RUBY_INPLACE_RE = re.compile(r"^-[pnlaw]*i")
PERL_CODE_FLAG_RE = re.compile(r"^-[a-zA-Z0-9]*[eE]$")

INTERPRETER_RE = re.compile(r"^(python(\d+(\.\d+)?)?|node|nodejs|deno|bun|ruby|perl|php)$")
INTERPRETER_LANG = {"python": "python", "node": "node", "nodejs": "node", "deno": "node", "bun": "node",
                    "ruby": "ruby", "perl": "perl", "php": "php"}

WRITE_INDICATORS = {
    "python": [
        r"\bopen\([^)]*['\"](?:[wax]\+?[bt]?|[bt][wax]\+?|r\+[bt]?|[bt]r\+)['\"]",
        r"\.write_text\(",
        r"\.write_bytes\(",
        r"\.open\(\s*(?:mode\s*=\s*)?['\"][wax]",
        r"\bjson\.dump\(",
        r"\bpickle\.dump\(",
        r"\bshutil\.(?:copy|copy2|copyfile|move)\(",
        r"\bos\.(?:rename|replace|remove|unlink|write)\(",
        r"inplace\s*=\s*True",
        r"\.to_csv\(",
        r"\.touch\(",
    ],
    "node": [
        r"\b(?:write|append)File(?:Sync)?\(",
        r"\bcreateWriteStream\(",
        r"\bfs\.(?:rename|copyFile|rm|unlink|truncate)(?:Sync)?\(",
        r"\bBun\.write\(",
        r"\bDeno\.(?:write|writeText|writeTextFile|writeFile|remove|rename)\b",
    ],
    "ruby": [
        r"\bFile\.(?:write|binwrite|open\([^)]*['\"][wa])",
        r"\bIO\.write\(",
        r"\bFileUtils\.",
    ],
    "perl": [
        r"\bopen\s*\(?[^;]*['\"]\s*>>?",
    ],
    "php": [
        r"\bfile_put_contents\(",
        r"\bfopen\([^)]*['\"][wax]",
    ],
}
STRING_LIT_RE = re.compile(r"'([^'\\]*(?:\\.[^'\\]*)*)'|\"([^\"\\]*(?:\\.[^\"\\]*)*)\"")
PATH_LIKE_RE = re.compile(r"/|\.\w{1,6}$")

XARGS_ARG_FLAGS = {"-I", "-n", "-P", "-L", "-d", "-s", "-E", "-a", "-i",
                   "--max-args", "--max-procs", "--max-lines", "--delimiter",
                   "--replace", "--arg-file", "--max-chars", "--eof"}
XARGS_BUNDLE_RE = re.compile(r"^-[InPLdsEai].+")
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}

# ---------------------------------------------------------------------------
# 理由文
# ---------------------------------------------------------------------------

REASON_REDIRECT = (
    "シェルのリダイレクト「{op} {target}」によるファイル書き込みは禁止です。"
    "新規作成は Write ツール、既存ファイルの変更は Edit ツールを使ってください。"
    "一時的な出力なら /tmp または $TMPDIR 配下に書き出してください。"
)
REASON_REDIRECT_VAR = (
    "リダイレクト先「{target}」が変数のため書き込み先を判定できません。"
    "一時ファイルでなければ Write / Edit ツールを使ってください。"
)
REASON_INPLACE = (
    "{tool} -i による単一ファイル「{file}」の書き換えは禁止です。"
    "Edit ツールで該当箇所を置換してください"
    "（複数ファイルへの一括置換のみ {tool} -i を許可しています）。"
)
REASON_WRITER = (
    "{tool} によるファイル「{file}」への書き込みは禁止です。Write / Edit ツールを使ってください。"
)
REASON_WRITER_VAR = (
    "{tool} の書き込み先「{file}」が変数のため判定できません。"
    "一時ファイルでなければ Write / Edit ツールを使ってください。"
)
REASON_INLINE = (
    "インライン {lang} スクリプトからのファイル書き込みは禁止です。"
    "Write / Edit ツールでファイルを変更してください。"
)
REASON_PATCH = "{tool} はワークツリーのファイルを直接書き換えます。意図した操作か確認してください。"

# ---------------------------------------------------------------------------
# データ型
# ---------------------------------------------------------------------------


@dataclass
class Token:
    kind: str  # "WORD" | "OP"
    value: str  # WORD: クォート除去後の値 / OP: 演算子
    raw: str = ""  # WORD: 元の文字列（置換抽出用）


@dataclass
class Segment:
    words: list = field(default_factory=list)
    writes: list = field(default_factory=list)  # (op, Token)
    heredoc_ids: list = field(default_factory=list)
    herestring: Optional[str] = None
    prev: Optional["Segment"] = None  # パイプで直前に繋がるセグメント


@dataclass(frozen=True)
class Ctx:
    full_cmd: str
    depth: int = 0
    bulk: bool = False
    loop: bool = False

    def child(self, **kw) -> "Ctx":
        return replace(self, depth=self.depth + 1, **kw)


@dataclass
class Decision:
    kind: str  # "deny" | "ask"
    reason: str


# ---------------------------------------------------------------------------
# スキャナ
# ---------------------------------------------------------------------------


def _skip_single(text: str, i: int) -> int:
    j = text.find("'", i + 1)
    return -1 if j < 0 else j + 1


def _skip_backtick(text: str, i: int) -> int:
    j = i + 1
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == "`":
            return j + 1
        j += 1
    return -1


def _skip_double(text: str, i: int) -> int:
    j = i + 1
    n = len(text)
    while j < n:
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == '"':
            return j + 1
        if c == "$" and text.startswith("$(", j):
            k = _skip_subst(text, j)
            if k < 0:
                return -1
            j = k
            continue
        if c == "`":
            k = _skip_backtick(text, j)
            if k < 0:
                return -1
            j = k
            continue
        j += 1
    return -1


def _skip_subst(text: str, i: int) -> int:
    """text[i:i+2] == "$(" から対応する ")" の直後までを返す。"""
    depth = 0
    j = i + 1
    n = len(text)
    while j < n:
        c = text[j]
        if c == "(":
            depth += 1
            j += 1
            continue
        if c == ")":
            depth -= 1
            j += 1
            if depth == 0:
                return j
            continue
        if c == "\\":
            j += 2
            continue
        if c == "'":
            k = _skip_single(text, j)
        elif c == '"':
            k = _skip_double(text, j)
        elif c == "`":
            k = _skip_backtick(text, j)
        else:
            j += 1
            continue
        if k < 0:
            return -1
        j = k
    return -1


def _unescape_double(s: str) -> str:
    return re.sub(r'\\(["\\$`])', r"\1", s)


def scan(text: str):
    """コマンド文字列を WORD / OP トークンに分解する。戻り値 (tokens, unbalanced)。"""
    tokens: list[Token] = []
    i = 0
    n = len(text)
    value: list[str] = []
    raw_start: Optional[int] = None

    def flush(end: int) -> None:
        nonlocal value, raw_start
        if raw_start is not None:
            tokens.append(Token("WORD", "".join(value), text[raw_start:end]))
        value = []
        raw_start = None

    while i < n:
        c = text[i]
        if c in " \t\r":
            flush(i)
            i += 1
            continue
        if raw_start is None:
            m = FD_REDIRECT_RE.match(text, i)
            if m:
                tokens.append(Token("OP", m.group(0), m.group(0)))
                i = m.end()
                continue
        op = next((o for o in OPERATORS if text.startswith(o, i)), None)
        if op is not None:
            flush(i)
            tokens.append(Token("OP", op, op))
            i += len(op)
            continue
        if raw_start is None:
            raw_start = i
        if c == "'":
            k = _skip_single(text, i)
            if k < 0:
                return tokens, True
            value.append(text[i + 1:k - 1])
            i = k
            continue
        if c == '"':
            k = _skip_double(text, i)
            if k < 0:
                return tokens, True
            value.append(_unescape_double(text[i + 1:k - 1]))
            i = k
            continue
        if c == "\\":
            if i + 1 < n:
                if text[i + 1] != "\n":
                    value.append(text[i + 1])
                i += 2
            else:
                i += 1
            continue
        if text.startswith("$(", i):
            k = _skip_subst(text, i)
            if k < 0:
                return tokens, True
            value.append(text[i:k])
            i = k
            continue
        if c == "`":
            k = _skip_backtick(text, i)
            if k < 0:
                return tokens, True
            value.append(text[i:k])
            i = k
            continue
        if text.startswith("${", i):
            k = text.find("}", i)
            if k < 0:
                return tokens, True
            value.append(text[i:k + 1])
            i = k + 1
            continue
        value.append(c)
        i += 1
    flush(n)
    return tokens, False


# ---------------------------------------------------------------------------
# heredoc / セグメント分割
# ---------------------------------------------------------------------------


def extract_heredocs(raw: str):
    """heredoc 本文を取り除き、演算子を <<__HD_n__ に置き換える。戻り値 (text, {id: body})。"""
    bodies: dict[str, str] = {}
    text = raw
    pos = 0
    count = 0
    while True:
        m = HEREDOC_RE.search(text, pos)
        if not m:
            break
        strip_tabs = m.group(1) == "-"
        delim = m.group(3)
        line_end = text.find("\n", m.end())
        if line_end < 0:
            pos = m.end()
            continue
        lines = text[line_end + 1:].split("\n")
        end_idx = None
        for idx, line in enumerate(lines):
            cand = line.lstrip("\t") if strip_tabs else line
            if cand == delim:
                end_idx = idx
                break
        if end_idx is None:
            pos = m.end()
            continue
        hid = f"__HD_{count}__"
        count += 1
        bodies[hid] = "\n".join(lines[:end_idx])
        after = "\n".join(lines[end_idx + 1:])
        text = text[:m.start()] + "<<" + hid + text[m.end():line_end + 1] + after
        pos = m.start() + len(hid) + 2
    return text, bodies


def strip_continuations(text: str) -> str:
    return text.replace("\\\n", " ")


def split_segments(tokens: list) :
    """トークン列を単純コマンド（Segment）に分割する。戻り値 (segments, loop_seen)。"""
    segments: list[Segment] = []
    cur = Segment()
    loop_seen = False
    pipe_from: Optional[Segment] = None
    i = 0
    n = len(tokens)

    def close(pipe_next: bool) -> None:
        nonlocal cur, pipe_from
        if cur.words or cur.writes or cur.heredoc_ids:
            cur.prev = pipe_from
            segments.append(cur)
            pipe_from = cur if pipe_next else None
        elif not pipe_next:
            pipe_from = None
        cur = Segment()

    while i < n:
        t = tokens[i]
        if t.kind == "WORD":
            if not cur.words and not cur.writes and t.value in SHELL_KEYWORDS and t.raw == t.value:
                if t.value in LOOP_KEYWORDS:
                    loop_seen = True
                i += 1
                continue
            cur.words.append(t)
            i += 1
            continue
        op = t.value
        if op in SEPARATOR_OPS:
            close(op in PIPE_OPS)
            i += 1
            continue
        m = REDIRECT_RE.match(op)
        if not m:
            i += 1
            continue
        fd, kind = m.group(1), m.group(2)
        target = tokens[i + 1] if i + 1 < n and tokens[i + 1].kind == "WORD" else None
        i += 2 if target is not None else 1
        if target is None:
            continue
        if kind == "<<<":
            cur.herestring = target.value
        elif kind == "<<":
            cur.heredoc_ids.append(target.value)
        elif kind in ("<", "<&"):
            pass
        elif kind in ("&>", "&>>"):
            cur.writes.append((op, target))
        elif kind in (">", ">>", ">|"):
            if fd in ("", "1"):
                cur.writes.append((op, target))
        elif kind == ">&":
            if fd in ("", "1") and not (target.value.isdigit() or target.value == "-"):
                cur.writes.append((op, target))
    close(False)
    return segments, loop_seen


# ---------------------------------------------------------------------------
# 補助
# ---------------------------------------------------------------------------


def base(word: Token) -> str:
    return os.path.basename(word.value)


def target_status(value: str, ctx: Ctx) -> str:
    """書き込み先の判定: "ok" | "ask" | "deny"。"""
    if value in ALLOWED_DEV or value.startswith(ALLOWED_DEV_PREFIXES):
        return "ok"
    if value.startswith(TEMP_PREFIXES):
        return "ok"
    if value.startswith("$(") or value.startswith("`"):
        return "ok" if "mktemp" in value else "ask"
    m = VAR_REF_RE.match(value)
    if m:
        if TEMP_VAR_NAME_RE.search(m.group(1)) or "mktemp" in ctx.full_cmd:
            return "ok"
        return "ask"
    return "deny"


def is_bulk(files: list, ctx: Ctx) -> bool:
    if ctx.bulk or len(files) >= 2:
        return True
    for f in files:
        if re.search(r"[*?\[]|\{\}", f) or "$(" in f or "`" in f:
            return True
    if ctx.loop and files and all(f.startswith("$") for f in files):
        return True
    return False


def heredoc_text(seg: Segment, heredocs: dict) -> str:
    parts = [heredocs.get(hid, "") for hid in seg.heredoc_ids]
    if seg.herestring:
        parts.append(seg.herestring)
    return "\n".join(p for p in parts if p)


def stdin_payload(seg: Segment, heredocs: dict) -> str:
    """セグメントの標準入力として渡されるテキスト（heredoc / herestring / 直前の echo 等）。"""
    parts = [heredoc_text(seg, heredocs)]
    prev = seg.prev
    if prev is not None and prev.words:
        pw = strip_wrappers(prev.words)
        if pw and base(pw[0]) in STDIN_PRODUCERS:
            parts.append(" ".join(w.value for w in pw[1:] if not w.value.startswith("-")))
            parts.append(heredoc_text(prev, heredocs))
    return "\n".join(p for p in parts if p)


def strip_wrappers(words: list) -> list:
    ws = list(words)
    while ws:
        v = ws[0].value
        if ASSIGNMENT_RE.match(v):
            ws.pop(0)
            continue
        name = os.path.basename(v)
        if name not in WRAPPERS:
            break
        arg_flags = WRAPPERS[name]
        ws.pop(0)
        while ws and ws[0].value.startswith("-") and ws[0].value != "-":
            flag = ws.pop(0).value
            if flag in arg_flags and ws:
                ws.pop(0)
        if name == "timeout" and ws and re.match(r"^\d+(\.\d+)?[smhd]?$", ws[0].value):
            ws.pop(0)
        if name == "env":
            while ws and ASSIGNMENT_RE.match(ws[0].value):
                ws.pop(0)
    return ws


def iter_substitutions(raw: str) -> list:
    """WORD の元文字列から $(...) / `...` の中身を列挙する（シングルクォート内は除く）。"""
    out: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        if raw.startswith("$((", i):
            k = _skip_subst(raw, i)
            i = k if k > 0 else n
            continue
        if raw.startswith("$(", i):
            k = _skip_subst(raw, i)
            if k < 0:
                break
            out.append(raw[i + 2:k - 1])
            i = k
            continue
        c = raw[i]
        if c == "`":
            k = _skip_backtick(raw, i)
            if k < 0:
                break
            out.append(raw[i + 1:k - 1])
            i = k
            continue
        if c == "\\":
            i += 2
            continue
        if c == "'":
            k = _skip_single(raw, i)
            i = k if k > 0 else n
            continue
        i += 1
    return out


# ---------------------------------------------------------------------------
# ルール
# ---------------------------------------------------------------------------


def check_redirects(seg: Segment, ctx: Ctx) -> list:
    out: list[Decision] = []
    for op, tok in seg.writes:
        st = target_status(tok.value, ctx)
        if st == "deny":
            out.append(Decision("deny", REASON_REDIRECT.format(op=op, target=tok.value)))
        elif st == "ask":
            out.append(Decision("ask", REASON_REDIRECT_VAR.format(target=tok.value)))
    return out


def check_substitutions(words: list, ctx: Ctx) -> list:
    out: list[Decision] = []
    for w in words:
        for inner in iter_substitutions(w.raw):
            out += analyze_text(inner, ctx.child())
    return out


def _shell_dash_c(words: list) -> Optional[str]:
    for idx in range(1, len(words)):
        v = words[idx].value
        if (v == "-c" or re.fullmatch(r"-[a-zA-Z]*c", v)) and idx + 1 < len(words):
            return words[idx + 1].value
    return None


def check_shell_recursion(seg: Segment, words: list, heredocs: dict, ctx: Ctx) -> list:
    name = base(words[0])
    if name in SHELLS or name == "su":
        code = _shell_dash_c(words)
        if code is None:
            if name == "su":
                return []
            positional = [w for w in words[1:] if not w.value.startswith("-") or w.value == "-"]
            if positional and positional[0].value != "-":
                return []  # bash script.sh
            code = stdin_payload(seg, heredocs)
        if not code:
            return []
        return analyze_text(code, ctx.child())
    if name == "eval":
        code = " ".join(w.value for w in words[1:])
        if re.fullmatch(r"\s*(?:\$\{?\w+\}?\s*)*", code):
            return []
        return analyze_text(code, ctx.child())
    if name == "xargs":
        rest = _strip_xargs_flags(words[1:])
        if not rest:
            return []
        return run_words(rest, heredocs, ctx.child(bulk=True))
    if name == "find":
        out: list[Decision] = []
        i = 1
        while i < len(words):
            if words[i].value in FIND_EXEC:
                j = i + 1
                sub: list[Token] = []
                while j < len(words) and words[j].value not in (";", "+"):
                    sub.append(words[j])
                    j += 1
                if sub:
                    out += run_words(sub, heredocs, ctx.child(bulk=True))
                i = j + 1
                continue
            i += 1
        return out
    return []


def _strip_xargs_flags(args: list) -> list:
    i = 0
    while i < len(args):
        a = args[i].value
        if not a.startswith("-") or a == "-":
            break
        if a in XARGS_ARG_FLAGS:
            i += 2
            continue
        i += 1  # boolean flag, --opt=value, or bundled value like -I{} / -n1
    return args[i:]


def parse_sed(args: list):
    inplace = False
    script_given = False
    files: list[str] = []
    i = 0
    while i < len(args):
        a = args[i].value
        if a == "--":
            files += [w.value for w in args[i + 1:]]
            break
        if a.startswith("-") and a != "-":
            if SED_INPLACE_RE.match(a) or a.startswith("--in-place"):
                inplace = True
                if a in ("-i", "-I") and i + 1 < len(args) and args[i + 1].value == "":
                    i += 1  # BSD sed: -i '' (空の接尾辞)
            if a in ("-e", "-f", "--expression", "--file"):
                script_given = True
                i += 2
                continue
            if a.startswith(("--expression=", "--file=")):
                script_given = True
            i += 1
            continue
        if not script_given:
            script_given = True
            i += 1
            continue
        files.append(a)
        i += 1
    return inplace, files


def parse_perl_like(args: list, inplace_re, arg_flags: set):
    inplace = False
    code_given = False
    files: list[str] = []
    i = 0
    while i < len(args):
        a = args[i].value
        if a == "--":
            files += [w.value for w in args[i + 1:]]
            break
        if a.startswith("-") and a != "-":
            if inplace_re.match(a):
                inplace = True
                # perl の -i は残りを接尾辞として消費する（-pie → -p -i.e）
                if PERL_CODE_FLAG_RE.match(a) and a.find("i") < a.rfind("e"):
                    i += 1
                    continue
            if PERL_CODE_FLAG_RE.match(a) and a[1] not in "MmIxCdD0lF":
                code_given = True
                i += 2
                continue
            if a in arg_flags:
                i += 2
                continue
            i += 1
            continue
        if not code_given:
            code_given = True  # スクリプトファイル
            i += 1
            continue
        files.append(a)
        i += 1
    return inplace, files


def parse_awk(args: list):
    inplace = False
    prog_given = False
    files: list[str] = []
    i = 0
    while i < len(args):
        a = args[i].value
        if a == "--":
            files += [w.value for w in args[i + 1:]]
            break
        if a.startswith("-") and a != "-":
            if a in ("-i", "--include"):
                if i + 1 < len(args) and args[i + 1].value == "inplace":
                    inplace = True
                i += 2
                continue
            if a in ("-iinplace", "--include=inplace", "--inplace"):
                inplace = True
                i += 1
                continue
            if a in ("-f", "--file", "-e", "--source"):
                prog_given = True
                i += 2
                continue
            if a in ("-v", "--assign", "-F", "--field-separator"):
                i += 2
                continue
            i += 1
            continue
        if not prog_given:
            prog_given = True
            i += 1
            continue
        if ASSIGNMENT_RE.match(a):
            i += 1
            continue
        files.append(a)
        i += 1
    return inplace, files


def check_inplace_editor(words: list, ctx: Ctx) -> list:
    name = base(words[0])
    args = words[1:]
    if name in ("sed", "gsed"):
        inplace, files = parse_sed(args)
    elif name == "perl":
        inplace, files = parse_perl_like(args, PERL_INPLACE_RE, set())
    elif name == "ruby":
        inplace, files = parse_perl_like(args, RUBY_INPLACE_RE, {"-r", "-I", "-C", "-E", "-F", "-x"})
    elif name in ("awk", "gawk", "mawk", "nawk"):
        inplace, files = parse_awk(args)
    else:
        return []
    if not inplace:
        return []
    if not files and not ctx.bulk:
        return []
    if is_bulk(files, ctx):
        return []
    return [Decision("deny", REASON_INPLACE.format(tool=name, file=files[0] if files else "?"))]


def check_tee_dd_truncate(words: list, ctx: Ctx) -> list:
    name = base(words[0])
    args = [w.value for w in words[1:]]
    targets: list[str] = []
    if name == "tee":
        targets = [a for a in args if not a.startswith("-")]
    elif name == "dd":
        targets = [a[3:] for a in args if a.startswith("of=")]
    elif name == "truncate":
        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-s", "--size", "-r", "--reference"):
                i += 2
                continue
            if a.startswith("-"):
                i += 1
                continue
            targets.append(a)
            i += 1
    else:
        return []
    out: list[Decision] = []
    for t in targets:
        st = target_status(t, ctx)
        if st == "deny":
            out.append(Decision("deny", REASON_WRITER.format(tool=name, file=t)))
        elif st == "ask":
            out.append(Decision("ask", REASON_WRITER_VAR.format(tool=name, file=t)))
    return out


def inline_script(seg: Segment, words: list, heredocs: dict):
    """インタプリタへ渡されるインラインスクリプトを返す。(lang, text) または None。"""
    name = base(words[0])
    if not INTERPRETER_RE.match(name):
        return None
    lang = INTERPRETER_LANG.get(name, "python" if name.startswith("python") else name)
    args = words[1:]
    code_parts: list[str] = []
    positional: Optional[str] = None
    i = 0

    if name == "deno":
        vals = [w.value for w in args]
        if vals and vals[0] == "eval":
            code = " ".join(v for v in vals[1:] if not v.startswith("-"))
            return (lang, code) if code else None
        return None

    while i < len(args):
        a = args[i].value
        nxt = args[i + 1].value if i + 1 < len(args) else None
        if a == "--":
            if nxt is not None:
                positional = nxt
            break
        if a.startswith("-") and a != "-":
            if lang == "python":
                if a == "-c" and nxt is not None:
                    code_parts.append(nxt)
                    i += 2
                    continue
                if a.startswith("-c") and len(a) > 2:
                    code_parts.append(a[2:])
                    i += 1
                    continue
                if a.startswith("-m"):
                    return None
                if a in ("-W", "-X") and nxt is not None:
                    i += 2
                    continue
            elif lang == "node":
                if a in ("-e", "--eval", "-p", "--print") and nxt is not None:
                    code_parts.append(nxt)
                    i += 2
                    continue
                if a.startswith(("--eval=", "--print=")):
                    code_parts.append(a.split("=", 1)[1])
                    i += 1
                    continue
                if a in ("-r", "--require", "--import", "--input-type") and nxt is not None:
                    i += 2
                    continue
            elif lang == "ruby":
                if (a == "-e" or re.fullmatch(r"-[a-zA-Z0-9]*e", a)) and nxt is not None:
                    code_parts.append(nxt)
                    i += 2
                    continue
                if a in ("-r", "-I", "-C", "-E", "-F", "-x") and nxt is not None:
                    i += 2
                    continue
            elif lang == "perl":
                if PERL_CODE_FLAG_RE.match(a) and a[1] not in "MmIxCdD0lF" and nxt is not None:
                    if not (PERL_INPLACE_RE.match(a) and a.find("i") < a.rfind("e")):
                        code_parts.append(nxt)
                        i += 2
                        continue
            elif lang == "php":
                if a == "-r" and nxt is not None:
                    code_parts.append(nxt)
                    i += 2
                    continue
                if a == "-f":
                    return None
            i += 1
            continue
        if a == "-":
            i += 1
            continue
        if code_parts:
            break  # スクリプトへの引数
        positional = a
        break

    if code_parts:
        return lang, "\n".join(code_parts)
    if positional is not None:
        return None  # スクリプトファイルの実行
    text = stdin_payload(seg, heredocs)
    return (lang, text) if text else None


def has_write_indicator(lang: str, text: str) -> bool:
    patterns = WRITE_INDICATORS.get(lang, [])
    if not any(re.search(p, text) for p in patterns):
        return False
    literals = [a or b for a, b in STRING_LIT_RE.findall(text)]
    paths = [s for s in literals if s and PATH_LIKE_RE.search(s)]
    if paths and all(s.startswith(TEMP_PREFIXES) or s.startswith("/dev/") for s in paths):
        return False  # 一時ファイルのみに書いている
    return True


def check_inline_interpreter(seg: Segment, words: list, heredocs: dict, ctx: Ctx) -> list:
    found = inline_script(seg, words, heredocs)
    if not found:
        return []
    lang, text = found
    if has_write_indicator(lang, text):
        return [Decision("deny", REASON_INLINE.format(lang=lang))]
    return []


def check_patch(words: list) -> list:
    name = base(words[0])
    vals = [w.value for w in words[1:]]
    if name == "patch":
        if any(v.startswith("--dry-run") for v in vals):
            return []
        return [Decision("ask", REASON_PATCH.format(tool="patch"))]
    if name == "git":
        i = 0
        while i < len(vals) and vals[i].startswith("-"):
            i += 2 if vals[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
        if i < len(vals) and vals[i] == "apply":
            rest = vals[i + 1:]
            if any(r in ("--check", "--stat", "--numstat", "--summary") for r in rest):
                return []
            return [Decision("ask", REASON_PATCH.format(tool="git apply"))]
    return []


# ---------------------------------------------------------------------------
# 解析の駆動
# ---------------------------------------------------------------------------


def run_rules(seg: Segment, heredocs: dict, ctx: Ctx) -> list:
    findings: list[Decision] = []
    findings += check_redirects(seg, ctx)
    findings += check_substitutions(seg.words, ctx)
    words = strip_wrappers(seg.words)
    if not words:
        return findings
    findings += check_shell_recursion(seg, words, heredocs, ctx)
    findings += check_inplace_editor(words, ctx)
    findings += check_tee_dd_truncate(words, ctx)
    findings += check_inline_interpreter(seg, words, heredocs, ctx)
    findings += check_patch(words)
    return findings


def run_words(words: list, heredocs: dict, ctx: Ctx) -> list:
    if ctx.depth > MAX_DEPTH:
        return []
    return run_rules(Segment(words=list(words)), heredocs, ctx)


def analyze_text(text: str, ctx: Ctx) -> list:
    if ctx.depth > MAX_DEPTH or not text.strip():
        return []
    text, heredocs = extract_heredocs(text)
    text = strip_continuations(text)
    tokens, unbalanced = scan(text)
    if unbalanced:
        return []  # bash 自身が構文エラーにするので何も書かれない
    segments, loop_seen = split_segments(tokens)
    if loop_seen and not ctx.loop:
        ctx = replace(ctx, loop=True)
    findings: list[Decision] = []
    for seg in segments:
        findings += run_rules(seg, heredocs, ctx)
    return findings


def worst(findings: list) -> Optional[Decision]:
    for kind in ("deny", "ask"):
        for f in findings:
            if f.kind == kind:
                return f
    return None


def evaluate(command: str) -> Optional[Decision]:
    """コマンド文字列を判定する。deny / ask の Decision、または None（判定なし）。"""
    return worst(analyze_text(command, Ctx(full_cmd=command)))


def emit(decision: Decision) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision.kind,
                    "permissionDecisionReason": decision.reason,
                }
            },
            ensure_ascii=False,
        )
    )


def main() -> int:
    if os.environ.get(DISABLE_ENV) == "1":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict) or data.get("tool_name") != "Bash":
        return 0
    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return 0
    try:
        decision = evaluate(command)
    except Exception:
        return 0  # fail-open
    if decision is not None:
        emit(decision)
    return 0


if __name__ == "__main__":
    sys.exit(main())
