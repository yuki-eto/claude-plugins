#!/usr/bin/env python3
"""Marp デッキと CSS を情報デザインの観点で検査する。

使い方: lint_deck.py <deck.md> [--theme theme.css ...] [--max-lines 8] [--max-chars 200]
"""

import argparse
import colorsys
import re
import sys
from collections import namedtuple

Finding = namedtuple("Finding", "path_index line rule message")

MIN_FONT_PX = 37
MIN_FONT_PT = 28
MAX_CHROMATIC_COLORS = 3

SEPARATOR_RE = re.compile(r"^\s*---\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
STYLE_OR_COMMENT_RE = re.compile(
    r"<style\b[^>]*>(.*?)</style\s*>|<!--(.*?)-->", re.DOTALL | re.IGNORECASE
)
DIRECTIVE_RE = re.compile(r"^[ \t]*(header|footer)[ \t]*:[ \t]*(.*?)[ \t]*$", re.MULTILINE)
FM_DIRECTIVE_RE = re.compile(r"^(header|footer)\s*:\s*(.*?)\s*$")
FM_STYLE_RE = re.compile(r"^style\s*:\s*(.*?)\s*$")

MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
HTML_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
HTML_ATTR_RE = re.compile(r"\b(alt|src)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]*>")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
LIST_MARKER_RE = re.compile(r"^\s*(?:>\s*)*(?:[-+*]|\d+[.)])\s+")
IMAGE_ONLY_RE = re.compile(r"\s*(?:!\[[^\]]*\]\([^)]*\)\s*)+")

CENTER_BODY_RES = [
    re.compile(r"<center\b", re.IGNORECASE),
    re.compile(r"\balign\s*=\s*[\"']?center", re.IGNORECASE),
    re.compile(r"text-align\s*:\s*center", re.IGNORECASE),
]

SMALL_FONT_EXEMPT_RE = re.compile(
    r"::?after|\.unit(?![\w-])|(?<![\w.#-])(?:footer|header|sup|sub|small|code)(?![\w-])",
    re.IGNORECASE,
)
TABLE_SELECTOR_RE = re.compile(r"(?<![\w.#-])(?:th|td|table)(?![\w-])", re.IGNORECASE)

COLOR_RE = re.compile(
    r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![0-9a-zA-Z_-])"
    r"|\b(rgba?|hsla?)\(([^)]*)\)",
    re.IGNORECASE,
)
URL_RE = re.compile(r"url\([^)]*\)", re.IGNORECASE)
GROUP_AT_RULES = ("@media", "@supports", "@layer", "@container", "@document")

Decl = namedtuple("Decl", "selector prop value line")


def strip_css_comments(text):
    return re.sub(
        r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.DOTALL
    )


def parse_css(text, base_line):
    text = strip_css_comments(text)
    decls = []
    stack = []
    buf = []
    state = {"line": base_line, "buf_line": None}
    depth = 0
    quote = None

    def add(ch):
        buf.append(ch)
        if state["buf_line"] is None and not ch.isspace():
            state["buf_line"] = state["line"]

    def emit():
        body = "".join(buf).strip()
        if body and stack and ":" in body:
            top = stack[-1]
            head = top.split()[0].lower() if top.startswith("@") else ""
            if head not in GROUP_AT_RULES:
                prop, _, value = body.partition(":")
                decls.append(
                    Decl(top, prop.strip().lower(), value.strip(), state["buf_line"])
                )
        del buf[:]
        state["buf_line"] = None

    for ch in text:
        if quote:
            add(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            add(ch)
        elif ch == "(":
            depth += 1
            add(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            add(ch)
        elif depth > 0:
            add(ch)
        elif ch == "{":
            prelude = " ".join("".join(buf).split())
            stack.append(prelude)
            del buf[:]
            state["buf_line"] = None
        elif ch in ";}":
            emit()
            if ch == "}" and stack:
                stack.pop()
        else:
            add(ch)
        if ch == "\n":
            state["line"] += 1
    return decls


def has_logo_image(text):
    return bool(find_logo_images(text))


def find_logo_images(text):
    found = []
    for m in MD_IMAGE_RE.finditer(text):
        src = m.group(2).strip().split()[0] if m.group(2).strip() else ""
        if "logo" in m.group(1).lower() or "logo" in src.lower():
            found.append(m.start())
    for m in HTML_IMG_RE.finditer(text):
        attrs = {k.lower(): v.strip("\"'") for k, v in HTML_ATTR_RE.findall(m.group(0))}
        if "logo" in attrs.get("alt", "").lower() or "logo" in attrs.get("src", "").lower():
            found.append(m.start())
    return found


class Slide:
    def __init__(self, first_line):
        self.first_line = first_line
        self.lines = []  # (lineno, text, kind) kind: text / fence / code
        self.css = []  # (css_text, base_line)
        self.directives = []  # (kind, value, lineno)

    def anchor_line(self):
        for no, text, _ in self.lines:
            if text.strip():
                return no
        return self.first_line


def split_front_matter(lines):
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[1:i], i + 1
    return [], 0


def parse_front_matter(fm_lines):
    css = []
    directives = []
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        lineno = i + 2
        m = FM_STYLE_RE.match(line)
        if m:
            value = m.group(1)
            if value[:1] in ("|", ">"):
                j = i + 1
                block = []
                while j < len(fm_lines) and (
                    not fm_lines[j].strip() or fm_lines[j][:1] in (" ", "\t")
                ):
                    block.append(fm_lines[j])
                    j += 1
                css.append(("\n".join(block), lineno + 1))
                i = j
                continue
            if value:
                css.append((value.strip("\"'"), lineno))
        else:
            m = FM_DIRECTIVE_RE.match(line)
            if m:
                directives.append((m.group(1), m.group(2), lineno))
        i += 1
    return css, directives


def split_slides(lines, start):
    slides = []
    current = Slide(start + 1)
    fence = None
    for idx in range(start, len(lines)):
        lineno = idx + 1
        text = lines[idx]
        if fence is None and SEPARATOR_RE.match(text):
            slides.append(current)
            current = Slide(lineno + 1)
            continue
        m = FENCE_RE.match(text)
        if fence is None:
            if m:
                fence = (m.group(1)[0], len(m.group(1)))
                current.lines.append((lineno, text, "fence"))
            else:
                current.lines.append((lineno, text, "text"))
        else:
            if (
                m
                and m.group(1)[0] == fence[0]
                and len(m.group(1)) >= fence[1]
                and not text.strip().strip(fence[0])
            ):
                fence = None
                current.lines.append((lineno, text, "fence"))
            else:
                current.lines.append((lineno, text, "code"))
    slides.append(current)
    return [s for s in slides if any(t.strip() for _, t, _ in s.lines)]


def extract_blocks(slide):
    original = "\n".join(t for _, t, _ in slide.lines)
    scan = "\n".join(t if k == "text" else " " * len(t) for _, t, k in slide.lines)
    chars = list(original)
    for m in STYLE_OR_COMMENT_RE.finditer(scan):
        start_line = slide.first_line + scan.count("\n", 0, m.start())
        if m.group(1) is not None:
            css_line = slide.first_line + scan.count("\n", 0, m.start(1))
            slide.css.append((original[m.start(1):m.end(1)], css_line))
        else:
            inner = original[m.start(2):m.end(2)]
            for d in DIRECTIVE_RE.finditer(inner):
                line = slide.first_line + scan.count("\n", 0, m.start(2)) + inner.count(
                    "\n", 0, d.start()
                )
                slide.directives.append((d.group(1), d.group(2), line))
        for pos in range(m.start(), m.end()):
            if chars[pos] != "\n":
                chars[pos] = "\0"
    cleaned = "".join(chars).split("\n")
    slide.lines = [
        (no, cleaned[i].replace("\0", ""), kind)
        for i, (no, _, kind) in enumerate(slide.lines)
    ]


def visible_line(text, kind):
    if kind == "fence":
        return ""
    if kind == "code":
        return text.strip()
    if "|" in text and TABLE_SEP_RE.match(text):
        return ""
    s = MD_IMAGE_RE.sub("", text)
    s = MD_LINK_RE.sub(r"\1", s)
    s = HTML_TAG_RE.sub("", s)
    s = LIST_MARKER_RE.sub("", s)
    s = re.sub(r"^\s*(?:>\s*)+", "", s)
    s = re.sub(r"[#*_`|]", "", s)
    return s.strip()


def counts_as_body_line(text, kind):
    if kind == "fence" or not text.strip():
        return False
    if kind == "code":
        return True
    if IMAGE_ONLY_RE.fullmatch(text):
        return False
    if not HTML_TAG_RE.sub("", text).strip():
        return False
    if "|" in text and TABLE_SEP_RE.match(text):
        return False
    return True


def parse_color(match):
    token = match.group(0).lower()
    if token.startswith("#"):
        h = token[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    func = match.group(1).lower()
    parts = [p for p in re.split(r"[,\s/]+", match.group(2).strip()) if p]
    if len(parts) < 3:
        return None
    try:
        if func.startswith("rgb"):
            rgb = []
            for p in parts[:3]:
                v = float(p[:-1]) * 2.55 if p.endswith("%") else float(p)
                rgb.append(int(round(min(255.0, max(0.0, v)))))
            return tuple(rgb)
        hue = float(re.sub(r"[a-zA-Z]+$", "", parts[0])) % 360 / 360.0
        sat = min(1.0, max(0.0, float(parts[1].rstrip("%")) / 100.0))
        lig = min(1.0, max(0.0, float(parts[2].rstrip("%")) / 100.0))
    except ValueError:
        return None
    r, g, b = colorsys.hls_to_rgb(hue, lig, sat)
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def is_chromatic(rgb):
    _, lig, sat = colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
    return sat >= 0.15 and 0.05 <= lig <= 0.95


def selector_parts(selector):
    parts, depth, cur = [], 0, []
    for ch in selector:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def lint_css(decls, path_index, findings):
    for d in decls:
        if d.prop == "font-size":
            m = re.match(r"^([\d.]+)(px|pt)\b", d.value.strip(), re.IGNORECASE)
            if m:
                size, unit = float(m.group(1)), m.group(2).lower()
                limit = MIN_FONT_PX if unit == "px" else MIN_FONT_PT
                parts = selector_parts(d.selector) or [d.selector]
                if size < limit and any(not SMALL_FONT_EXEMPT_RE.search(p) for p in parts):
                    findings.append(
                        Finding(
                            path_index,
                            d.line,
                            "small-font",
                            "font-size %s%s は小さすぎる（%dpx / %dpt 以上にする）。対象: %s"
                            % (m.group(1), unit, MIN_FONT_PX, MIN_FONT_PT, d.selector),
                        )
                    )
        elif d.prop == "text-align" and d.value.strip().lower().startswith("center"):
            parts = selector_parts(d.selector) or [d.selector]
            if any(not TABLE_SELECTOR_RE.search(p) for p in parts):
                findings.append(
                    Finding(
                        path_index,
                        d.line,
                        "centered-text",
                        "text-align: center は使わず左揃えにする。対象: %s" % d.selector,
                    )
                )


def collect_colors(sources):
    """sources: [(path_index, decls)] を出現順に走査し (path_index, line, rgb) を返す。"""
    found = []
    for path_index, decls in sources:
        for d in decls:
            value = URL_RE.sub("", d.value)
            for m in COLOR_RE.finditer(value):
                rgb = parse_color(m)
                if rgb is not None:
                    found.append((path_index, d.line, rgb))
    return found


def lint_colors(color_hits, findings):
    seen = []
    fourth = None
    for path_index, line, rgb in color_hits:
        if rgb in seen or not is_chromatic(rgb):
            continue
        seen.append(rgb)
        if len(seen) == MAX_CHROMATIC_COLORS + 1:
            fourth = (path_index, line, rgb)
    if fourth:
        findings.append(
            Finding(
                fourth[0],
                fourth[1],
                "too-many-colors",
                "有彩色が %d 種類ある（上限 %d: ベース/メイン/アクセント）。%d 種類目: #%02X%02X%02X"
                % (len(seen), MAX_CHROMATIC_COLORS, MAX_CHROMATIC_COLORS + 1, *fourth[2]),
            )
        )


def lint_slides(slides, max_lines, max_chars, findings):
    logo_slides = []
    for slide in slides:
        anchor = slide.anchor_line()
        body = slide.lines

        line_count = sum(1 for _, t, k in body if counts_as_body_line(t, k))
        if line_count > max_lines:
            findings.append(
                Finding(
                    0,
                    anchor,
                    "too-many-lines",
                    "本文が %d 行ある（上限 %d 行）。1 枚の情報量を絞るか分割する" % (line_count, max_lines),
                )
            )

        visible = [visible_line(t, k) for _, t, k in body]
        visible_nonempty = [v for v in visible if v]
        joined = "\n".join(visible_nonempty)
        char_count = len(re.sub(r"\s+", "", joined))
        if char_count > max_chars:
            findings.append(
                Finding(
                    0,
                    anchor,
                    "too-many-chars",
                    "可視テキストが %d 文字ある（上限 %d 文字）。1 枚の情報量を絞るか分割する"
                    % (char_count, max_chars),
                )
            )

        compact = re.sub(r"\s+", "", joined).lower()
        if ("ご清聴" in compact or "thankyou" in compact) and len(visible_nonempty) <= 2:
            findings.append(
                Finding(
                    0,
                    anchor,
                    "thanks-slide",
                    "「ご清聴ありがとうございました」だけのスライドは作らず、まとめスライドにする",
                )
            )

        slide_logos = []
        for no, text, kind in body:
            if kind != "text":
                continue
            if any(rx.search(text) for rx in CENTER_BODY_RES):
                findings.append(
                    Finding(
                        0,
                        no,
                        "centered-text",
                        "中央揃え（<center> / align=\"center\" / text-align: center）は使わず左揃えにする",
                    )
                )
            for _ in find_logo_images(text):
                slide_logos.append(no)
        if slide_logos:
            logo_slides.append(slide_logos)

    for slide_logos in logo_slides[1:]:
        for no in slide_logos:
            findings.append(
                Finding(
                    0,
                    no,
                    "logo-repeated",
                    "ロゴが 2 枚目以降のスライドにも出ている。ロゴは表紙だけに置く",
                )
            )


def lint(deck_path, deck_text, themes, max_lines=8, max_chars=200):
    """themes: [(path, css_text)]。戻り値は (paths, findings)。paths[0] がデッキ。"""
    paths = [deck_path] + [p for p, _ in themes]
    findings = []

    lines = deck_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    fm_lines, body_start = split_front_matter(lines)
    fm_css, fm_directives = parse_front_matter(fm_lines)
    slides = split_slides(lines, body_start)
    for slide in slides:
        extract_blocks(slide)

    css_sources = []
    for i, (_, css_text) in enumerate(themes):
        css_sources.append((i + 1, parse_css(css_text, 1)))
    for css_text, base in fm_css:
        css_sources.append((0, parse_css(css_text, base)))
    for slide in slides:
        for css_text, base in slide.css:
            css_sources.append((0, parse_css(css_text, base)))

    for path_index, decls in css_sources:
        lint_css(decls, path_index, findings)
    lint_colors(collect_colors(css_sources), findings)

    lint_slides(slides, max_lines, max_chars, findings)

    directives = list(fm_directives)
    for slide in slides:
        directives.extend(slide.directives)
    for kind, value, line in directives:
        if has_logo_image(value):
            findings.append(
                Finding(
                    0,
                    line,
                    "logo-repeated",
                    "%s ディレクティブにロゴ画像があり全ページに表示される。ロゴは表紙だけに置く" % kind,
                )
            )

    findings.sort(key=lambda f: (f.path_index, f.line, f.rule))
    return paths, findings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Marp デッキの情報デザイン lint")
    parser.add_argument("deck", help="検査する Marp の Markdown")
    parser.add_argument("--theme", nargs="+", action="extend", default=[], help="追加で検査する CSS")
    parser.add_argument("--max-lines", type=int, default=8)
    parser.add_argument("--max-chars", type=int, default=200)
    args = parser.parse_args(argv)

    try:
        with open(args.deck, encoding="utf-8") as f:
            deck_text = f.read()
        themes = []
        for path in args.theme:
            with open(path, encoding="utf-8") as f:
                themes.append((path, f.read()))
    except (OSError, UnicodeDecodeError) as e:
        print("読み込めません: %s" % e, file=sys.stderr)
        return 2

    paths, findings = lint(args.deck, deck_text, themes, args.max_lines, args.max_chars)
    for f in findings:
        print("%s:%d: [%s] %s" % (paths[f.path_index], f.line, f.rule, f.message))
    if findings:
        print("%d 件の指摘" % len(findings))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
