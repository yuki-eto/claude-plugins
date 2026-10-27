import contextlib
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lint_deck  # noqa: E402


def run(deck, themes=(), max_lines=8, max_chars=200):
    _, findings = lint_deck.lint(
        "deck.md", deck, [("t%d.css" % i, c) for i, c in enumerate(themes)], max_lines, max_chars
    )
    return findings


def rules(findings):
    return [f.rule for f in findings]


class RuleTests(unittest.TestCase):
    def test_too_many_lines(self):
        deck = "# T\n" + "\n".join("- 項目%d" % i for i in range(9)) + "\n"
        self.assertIn("too-many-lines", rules(run(deck)))
        self.assertNotIn("too-many-lines", rules(run("# T\n\n- a\n- b\n")))

    def test_image_only_lines_not_counted(self):
        deck = "# T\n" + "![a](a.png)\n" * 10 + "- a\n"
        self.assertNotIn("too-many-lines", rules(run(deck)))

    def test_too_many_chars(self):
        deck = "# T\n\n" + "あ" * 201 + "\n"
        self.assertIn("too-many-chars", rules(run(deck)))
        self.assertNotIn("too-many-chars", rules(run("# T\n\n" + "あ" * 50 + "\n")))

    def test_chars_ignore_markup(self):
        deck = "# T\n\n" + "**" + "あ" * 100 + "**" + "[x](http://example.com/" + "a" * 300 + ")\n"
        self.assertNotIn("too-many-chars", rules(run(deck)))

    def test_small_font(self):
        self.assertIn("small-font", rules(run("# T\n", ["p { font-size: 20px; }"])))
        self.assertIn("small-font", rules(run("# T\n", ["p { font-size: 18pt; }"])))
        self.assertNotIn("small-font", rules(run("# T\n", ["p { font-size: 37px; }"])))
        self.assertNotIn("small-font", rules(run("# T\n", ["p { font-size: 28pt; }"])))
        self.assertNotIn("small-font", rules(run("# T\n", ["p { font-size: 0.5em; }"])))

    def test_small_font_exempt_selectors(self):
        css = "footer, header, section::after { font-size: 20px; }\n.unit { font-size: 16px; }\ncode { font-size: 20px; }"
        self.assertNotIn("small-font", rules(run("# T\n", [css])))

    def test_small_font_line_number(self):
        f = [x for x in run("# T\n", ["a { color: #000; }\n\np { font-size: 10px; }"]) if x.rule == "small-font"]
        self.assertEqual(f[0].line, 3)
        self.assertEqual(f[0].path_index, 1)

    def test_centered_text_css(self):
        self.assertIn("centered-text", rules(run("# T\n", ["h1 { text-align: center; }"])))
        self.assertNotIn("centered-text", rules(run("# T\n", ["h1 { text-align: left; }"])))

    def test_centered_text_table_exempt(self):
        css = "th { text-align: center; }\ntable td { text-align: center; }"
        self.assertNotIn("centered-text", rules(run("# T\n", [css])))

    def test_centered_text_html(self):
        self.assertIn("centered-text", rules(run("# T\n\n<center>x</center>\n")))
        self.assertIn("centered-text", rules(run('# T\n\n<p align="center">x</p>\n')))
        self.assertIn("centered-text", rules(run('# T\n\n<p style="text-align: center">x</p>\n')))
        self.assertNotIn("centered-text", rules(run("# T\n\nx\n")))

    def test_thanks_slide(self):
        self.assertIn("thanks-slide", rules(run("# T\n\n---\n\n# ご清聴ありがとうございました\n")))
        self.assertIn("thanks-slide", rules(run("# T\n\n---\n\n# Thank You\n")))
        deck = "# T\n\n---\n\n# まとめ\n\n- ご清聴に感謝\n- a\n- b\n"
        self.assertNotIn("thanks-slide", rules(run(deck)))

    def test_too_many_colors(self):
        css = ":root { --a: #ff0000; --b: #00ff00; --c: #0000ff; }"
        self.assertNotIn("too-many-colors", rules(run("# T\n", [css])))
        css4 = css + "\np { color: #ff00ff; }"
        f = [x for x in run("# T\n", [css4]) if x.rule == "too-many-colors"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].line, 2)

    def test_achromatic_not_counted(self):
        css = (
            ":root { --a: #ff0000; --b: #00ff00; --c: #0000ff; }\n"
            "p { color: #222; background: #FFFFFF; border-color: rgb(107,107,107); x: hsl(0, 0%, 50%); }"
        )
        self.assertNotIn("too-many-colors", rules(run("# T\n", [css])))

    def test_colors_normalized(self):
        css = "a { color: #f00; } b { color: rgb(255, 0, 0); } c { color: hsl(0, 100%, 50%); } d { color: #00f; } e { color: #0f0; }"
        self.assertNotIn("too-many-colors", rules(run("# T\n", [css])))

    def test_logo_repeated(self):
        deck = "# T\n\n![logo](logo.png)\n\n---\n\n# A\n\n![logo](logo.png)\n"
        f = [x for x in run(deck) if x.rule == "logo-repeated"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].line, 9)

    def test_logo_single_slide_ok(self):
        deck = "# T\n\n![logo](logo.png)\n\n---\n\n# A\n\n![fig](a.png)\n"
        self.assertNotIn("logo-repeated", rules(run(deck)))

    def test_logo_html_img(self):
        deck = '# T\n\n<img src="a/logo.svg">\n\n---\n\n# A\n\n<img src="x.png" alt="Logo">\n'
        self.assertIn("logo-repeated", rules(run(deck)))

    def test_logo_in_header_directive(self):
        deck = "# T\n\n<!-- header: ![logo](logo.png) -->\n\n- a\n"
        f = [x for x in run(deck) if x.rule == "logo-repeated"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].line, 3)

    def test_logo_in_front_matter_footer(self):
        deck = "---\nmarp: true\nfooter: '![logo](logo.png)'\n---\n\n# T\n"
        f = [x for x in run(deck) if x.rule == "logo-repeated"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].line, 3)

    def test_non_logo_header_ok(self):
        deck = "# T\n\n<!-- header: 社内資料 -->\n\n- a\n"
        self.assertNotIn("logo-repeated", rules(run(deck)))


class ParseTests(unittest.TestCase):
    def test_front_matter_style_is_css(self):
        deck = "---\nmarp: true\nstyle: |\n  p { font-size: 10px; }\n---\n\n# T\n"
        f = [x for x in run(deck) if x.rule == "small-font"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].line, 4)
        self.assertEqual(f[0].path_index, 0)

    def test_front_matter_not_counted_as_slide(self):
        deck = "---\nmarp: true\ntheme: x\n---\n\n# T\n\n- a\n"
        self.assertEqual(run(deck), [])

    def test_style_tag_extracted_and_excluded_from_body(self):
        style = "<style>\n" + "p { color: red; }\n" * 20 + "</style>\n"
        deck = "# T\n\n" + style + "- a\n"
        self.assertNotIn("too-many-lines", rules(run(deck)))
        deck2 = "# T\n\n<style scoped>\np { font-size: 12px; }\n</style>\n"
        f = [x for x in run(deck2) if x.rule == "small-font"]
        self.assertEqual(f[0].line, 4)

    def test_comment_excluded_from_body(self):
        deck = "# T\n\n<!--\n" + "memo\n" * 20 + "-->\n- a\n"
        self.assertNotIn("too-many-lines", rules(run(deck)))
        self.assertNotIn("too-many-chars", rules(run(deck)))

    def test_separator_in_code_fence_does_not_split(self):
        deck = "# T\n\n```\na\n---\nb\n```\n\n---\n\n# ご清聴ありがとうございました\n"
        f = [x for x in run(deck) if x.rule == "thanks-slide"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].line, 11)

    def test_separator_in_tilde_fence(self):
        deck = "# T\n\n~~~\n---\n~~~\n\n- a\n- b\n- c\n- d\n"
        self.assertEqual(rules(run(deck, max_lines=100)), [])

    def test_multiple_slides_line_numbers(self):
        deck = "# A\n\n---\n\n# B\n\n" + "\n".join("- x%d" % i for i in range(9)) + "\n"
        f = [x for x in run(deck) if x.rule == "too-many-lines"]
        self.assertEqual(f[0].line, 5)

    def test_media_query_nested(self):
        css = "@media print { p { font-size: 12px; } }"
        f = [x for x in run("# T\n", [css]) if x.rule == "small-font"]
        self.assertEqual(len(f), 1)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text):
        path = os.path.join(self.dir.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def invoke(self, argv):
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = lint_deck.main(argv)
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_exit_0_and_no_output(self):
        deck = self.write("ok.md", "# タイトル\n\n- a\n- b\n")
        code, out, _ = self.invoke([deck])
        self.assertEqual((code, out), (0, ""))

    def test_exit_1_with_summary(self):
        deck = self.write("ng.md", "# T\n\n---\n\n# ご清聴ありがとうございました\n")
        code, out, _ = self.invoke([deck])
        self.assertEqual(code, 1)
        lines = out.strip().split("\n")
        self.assertEqual(lines[0], "%s:5: [thanks-slide] %s" % (deck, lines[0].split("] ", 1)[1]))
        self.assertEqual(lines[-1], "1 件の指摘")

    def test_theme_option(self):
        deck = self.write("ok.md", "# T\n")
        css = self.write("t.css", "p { font-size: 10px; }\n")
        code, out, _ = self.invoke([deck, "--theme", css])
        self.assertEqual(code, 1)
        self.assertIn("%s:1: [small-font]" % css, out)

    def test_thresholds(self):
        deck = self.write("d.md", "# T\n\n- a\n- b\n- c\n")
        self.assertEqual(self.invoke([deck, "--max-lines", "3"])[0], 1)
        self.assertEqual(self.invoke([deck, "--max-lines", "4"])[0], 0)

    def test_missing_file_exit_2(self):
        code, _, _ = self.invoke([os.path.join(self.dir.name, "none.md")])
        self.assertEqual(code, 2)

    def test_missing_theme_exit_2(self):
        deck = self.write("ok.md", "# T\n")
        code, _, _ = self.invoke([deck, "--theme", os.path.join(self.dir.name, "none.css")])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
