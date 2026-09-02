#!/usr/bin/env python3
"""guard.py のテーブル駆動テスト。

実行:
  python3 -m unittest discover -s plugins/no-shell-edit/hooks -p 'test_*.py'
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import guard  # noqa: E402

GUARD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard.py")

# (command, expected)  expected: None (pass) | "deny" | "ask"
CASES = [
    # --- 通常の作業（誤検知しないこと） ---
    ("grep '>' file", None),
    ("git commit -m \"a > b\"", None),
    ("git commit -m \"$(cat <<'EOF'\nfeat: x\n\nCo-Authored-By: A <a@b.c>\nEOF\n)\"", None),
    ("gh pr create --title t --body \"$(cat <<'EOF'\n## Summary\n> quote\nEOF\n)\"", None),
    ("ls > /dev/null 2>&1", None),
    ("make 2>&1 | tee /tmp/build.log", None),
    ("ls 2>err.log", None),
    ("npm test 2>&1 | tail -20", None),
    ("cat <<EOF\nhello\nEOF", None),
    ("cat <<EOF | tee /dev/tty\nx\nEOF", None),
    ("cmd > /tmp/out.json", None),
    ("cmd > \"$TMPDIR/x\"", None),
    ("cmd > \"${TMPDIR}/x\"", None),
    ("tmp=$(mktemp); cmd > \"$tmp\"", None),
    ("cmd > \"$(mktemp)\"", None),
    ("sed 's/a/b/' file | head", None),
    ("sed -n '1,5p' file", None),
    ("perl -ne 'print if /x/' file", None),
    ("awk '{print > \"/tmp/x\"}' f", None),
    ("python3 -c \"print(open('f').read())\"", None),
    ("python3 script.py", None),
    ("python3 -m pytest", None),
    ("python3 --version", None),
    ("python3 -c \"import json; json.dump(d, open('/tmp/x.json','w'))\"", None),
    ("node -e \"console.log(require('./package.json').version)\"", None),
    ("ruby -e 'puts 1'", None),
    ("eval \"$cmd\"", None),
    ("patch --dry-run -p1 < fix.patch", None),
    ("git apply --check x.diff", None),
    ("git apply --stat x.diff", None),
    ("git -C sub apply --check x.diff", None),
    ("prettier --write src/", None),
    ("gofmt -w .", None),
    ("eslint --fix .", None),
    ("npm install", None),
    ("cargo fmt", None),
    ("git commit -am x", None),
    ("find . -name x -exec rm {} +", None),
    ("curl -o out.json https://example.com", None),
    ("cp a b", None),
    ("echo 'unterminated > f", None),
    ("bash script.sh", None),
    ("xargs -n1 echo", None),
    ("kubectl apply -f - <<EOF\napiVersion: v1\nEOF", None),
    ("if [ -f x ]; then echo yes; fi", None),
    ("(cd sub && make) > /tmp/build.log", None),
    ("echo 2 > /dev/null", None),
    # --- 一括置換の例外（通ること） ---
    ("sed -i 's/a/b/' a.py b.py", None),
    ("sed -i 's/a/b/' src/*.py", None),
    ("sed -i 's/a/b/' $(git ls-files '*.py')", None),
    ("grep -rl foo . | xargs sed -i 's/foo/bar/'", None),
    ("find . -name '*.py' -exec sed -i 's/a/b/' {} +", None),
    ("find . -name '*.py' -exec sed -i 's/a/b/' {} \\;", None),
    ("for f in *.py; do sed -i 's/a/b/' \"$f\"; done", None),
    ("while read f; do sed -i 's/a/b/' \"$f\"; done < list.txt", None),
    ("perl -pi -e 's/a/b/' a.txt b.txt", None),
    # --- リダイレクト ---
    ("echo hi > out.txt", "deny"),
    ("printf 'x\\n' >> src/a.py", "deny"),
    ("cat > file.md <<EOF\nbody\nEOF", "deny"),
    ("cat <<EOF > file.md\nbody\nEOF", "deny"),
    ("cat <<EOF | sudo tee /etc/hosts\nx\nEOF", "deny"),
    ("echo \"$(echo x > y)\"", "deny"),
    (": > file.txt", "deny"),
    ("cmd &> out.log", "deny"),
    ("cmd >| out.txt", "deny"),
    ("{ echo a; echo b; } > out.txt", "deny"),
    ("cmd > \"$OUT\"", "ask"),
    # --- in-place エディタ ---
    ("sed -i 's/a/b/' file.py", "deny"),
    ("sed -i '' 's/a/b/' file.py", "deny"),
    ("sed -i.bak -e 's/a/b/' file.py", "deny"),
    ("sed --in-place 's/a/b/' file.py", "deny"),
    ("sed -Ei 's/a+/b/' file.py", "deny"),
    ("gsed -i 's/a/b/' file.py", "deny"),
    ("sed -i 's/a/b/' \"$file\"", "deny"),
    ("perl -pi -e 's/a/b/' file", "deny"),
    ("perl -i.bak -pe 's/a/b/' file", "deny"),
    ("ruby -pi -e 'gsub(/a/,\"b\")' file", "deny"),
    ("gawk -i inplace '{print}' file", "deny"),
    ("sudo sed -i 's/a/b/' /etc/hosts", "deny"),
    # --- tee / dd / truncate ---
    ("echo x | tee out.txt", "deny"),
    ("echo x | tee -a out.txt", "deny"),
    ("dd if=/dev/zero of=img.bin", "deny"),
    ("truncate -s 0 file", "deny"),
    # --- インラインスクリプト ---
    ("python3 -c \"open('f','w').write('x')\"", "deny"),
    ("python3 -c \"from pathlib import Path; Path('a').write_text('x')\"", "deny"),
    ("python3 - <<EOF\nfrom pathlib import Path\nPath('a').write_text('x')\nEOF", "deny"),
    ("python3 <<'EOF'\nwith open('out.txt', 'w') as f:\n    f.write('x')\nEOF", "deny"),
    ("echo \"import json; json.dump({}, open('c.json','w'))\" | python3", "deny"),
    ("python -c \"open('/tmp/x','w').write('hello world')\"", None),
    ("node -e \"require('fs').writeFileSync('a.js','x')\"", "deny"),
    ("node - <<EOF\nconst fs = require('fs'); fs.writeFileSync('a.js', 'x')\nEOF", "deny"),
    ("ruby -e 'File.write(\"a.rb\", \"x\")'", "deny"),
    ("perl -e 'open(my $fh, \">\", \"a.txt\"); print $fh \"x\"'", "deny"),
    ("php -r 'file_put_contents(\"a.php\", \"x\");'", "deny"),
    # --- シェル再帰 ---
    ("bash -c \"echo x > f\"", "deny"),
    ("sh -c 'sed -i s/a/b/ file.py'", "deny"),
    ("xargs -I{} sh -c 'echo x > {}'", "deny"),
    ("eval 'echo x > f'", "deny"),
    ("bash <<EOF\necho x > f\nEOF", "deny"),
    ("echo 'echo x > f' | sh", "deny"),
    ("nohup bash -c 'echo x > f'", "deny"),
    ("find . -name '*.py' -exec sh -c 'echo x > {}' \\;", "deny"),
    # --- patch / git apply ---
    ("patch -p1 < fix.patch", "ask"),
    ("git apply x.diff", "ask"),
    ("git -C sub apply x.diff", "ask"),
]


class EvaluateTest(unittest.TestCase):
    def test_table(self):
        for command, expected in CASES:
            with self.subTest(command=command):
                decision = guard.evaluate(command)
                actual = decision.kind if decision else None
                self.assertEqual(
                    actual,
                    expected,
                    f"\ncommand: {command!r}\nreason: {decision.reason if decision else None}",
                )

    def test_deny_beats_ask(self):
        decision = guard.evaluate("cmd > \"$OUT\"; echo x > f")
        self.assertEqual(decision.kind, "deny")

    def test_reason_mentions_target(self):
        decision = guard.evaluate("echo hi > out.txt")
        self.assertIn("out.txt", decision.reason)
        decision = guard.evaluate("sed -i 's/a/b/' file.py")
        self.assertIn("file.py", decision.reason)
        self.assertIn("Edit", decision.reason)


class ScannerTest(unittest.TestCase):
    def test_fd_redirect_tokens(self):
        tokens, unbalanced = guard.scan("ls 2>&1 >/dev/null")
        self.assertFalse(unbalanced)
        self.assertEqual([t.value for t in tokens], ["ls", "2>&", "1", ">", "/dev/null"])

    def test_substitution_kept_in_word(self):
        tokens, _ = guard.scan("echo \"$(echo a; echo b)\" done")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[1].value, "$(echo a; echo b)")

    def test_heredoc_extraction(self):
        text, bodies = guard.extract_heredocs("cat <<EOF > f\nline1\nline2\nEOF\necho after")
        self.assertEqual(text, "cat <<__HD_0__ > f\necho after")
        self.assertEqual(bodies["__HD_0__"], "line1\nline2")

    def test_unbalanced(self):
        _, unbalanced = guard.scan("echo 'abc")
        self.assertTrue(unbalanced)


class MainTest(unittest.TestCase):
    def run_hook(self, stdin_text, env=None):
        full_env = dict(os.environ)
        full_env.pop(guard.DISABLE_ENV, None)
        if env:
            full_env.update(env)
        proc = subprocess.run(
            [sys.executable, GUARD_PATH],
            input=stdin_text,
            capture_output=True,
            text=True,
            env=full_env,
        )
        return proc

    def test_deny_output(self):
        proc = self.run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo hi > out.txt"}}))
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("out.txt", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_pass_has_no_output(self):
        proc = self.run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la"}}))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_other_tool_ignored(self):
        proc = self.run_hook(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "x"}}))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_malformed_json(self):
        proc = self.run_hook("not json")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_disable_env(self):
        proc = self.run_hook(
            json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo hi > out.txt"}}),
            env={guard.DISABLE_ENV: "1"},
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
