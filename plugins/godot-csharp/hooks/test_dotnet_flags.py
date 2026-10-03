#!/usr/bin/env python3
"""dotnet_flags.py のテスト。

実行:
  python3 -m unittest discover -s plugins/godot-csharp/hooks -p 'test_*.py'
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HOOK_DIR)

import dotnet_flags  # noqa: E402

HOOK_PATH = os.path.join(HOOK_DIR, "dotnet_flags.py")
FULL = "-m:1 -nodeReuse:false --disable-build-servers"


class EvaluateTest(unittest.TestCase):
    def test_no_flags_build(self):
        out = dotnet_flags.evaluate("dotnet build godot/X.sln")
        self.assertIsNotNone(out)
        for flag in ("-m:1", "-nodeReuse:false", "--disable-build-servers"):
            self.assertIn(flag, out)
        self.assertNotIn("vstest", out)

    def test_all_flags(self):
        self.assertIsNone(dotnet_flags.evaluate(f"dotnet build godot/X.sln {FULL}"))

    def test_partial_test(self):
        out = dotnet_flags.evaluate("cd godot && dotnet test foo.csproj -m:1")
        self.assertIsNotNone(out)
        self.assertIn("vstest", out)
        self.assertIn("--no-build", out)
        self.assertTrue(out.startswith("`dotnet test` に -nodeReuse:false --disable-build-servers"))

    def test_test_without_no_build(self):
        out = dotnet_flags.evaluate(f"dotnet test x.sln {FULL}")
        self.assertIsNotNone(out)
        self.assertTrue(out.startswith("`dotnet test` に --no-build"))
        self.assertIn("vstest", out)

    def test_test_with_no_build(self):
        self.assertIsNone(dotnet_flags.evaluate(f"dotnet test x.sln {FULL} --no-build"))

    def test_test_bare(self):
        out = dotnet_flags.evaluate("dotnet test x.sln")
        self.assertIsNotNone(out)
        for text in ("-m:1", "--no-build", "vstest"):
            self.assertIn(text, out)

    def test_run_and_new_ignored(self):
        self.assertIsNone(dotnet_flags.evaluate("dotnet run --project tools/X -- sync"))
        self.assertIsNone(dotnet_flags.evaluate("dotnet new console"))

    def test_msbuild_slash_form(self):
        self.assertIsNone(
            dotnet_flags.evaluate("dotnet build x.sln /m:1 /nodeReuse:false --disable-build-servers")
        )

    def test_case_insensitive(self):
        self.assertIsNone(
            dotnet_flags.evaluate("dotnet test x.sln -maxcpucount:1 -NODEREUSE:FALSE --Disable-Build-Servers --No-Build")
        )

    def test_not_command_position(self):
        self.assertIsNone(dotnet_flags.evaluate("echo dotnet build"))
        self.assertIsNone(dotnet_flags.evaluate("grep 'dotnet build; x' README.md"))

    def test_env_assignment_prefix(self):
        self.assertIsNotNone(dotnet_flags.evaluate("FOO=1 dotnet build x.sln"))

    def test_full_path_dotnet(self):
        self.assertIsNotNone(dotnet_flags.evaluate("/usr/local/share/dotnet/dotnet build x.sln"))

    def test_multiple_segments(self):
        out = dotnet_flags.evaluate(f"dotnet build a.sln {FULL} && dotnet test a.sln")
        self.assertIsNotNone(out)
        self.assertIn("`dotnet test`", out)
        self.assertNotIn("`dotnet build` に", out)

    def test_redirect_is_not_separator(self):
        self.assertIsNotNone(dotnet_flags.evaluate("dotnet build x.sln 2>&1 | tail -5"))
        self.assertIsNone(dotnet_flags.evaluate(f"dotnet build x.sln {FULL} 2>&1 | tail -5"))

    def test_unparsable(self):
        self.assertIsNone(dotnet_flags.evaluate("dotnet build 'unterminated"))


class HookProcessTest(unittest.TestCase):
    def run_hook(self, command, project_dir=None, stdin_text=None, extra=None):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        if project_dir is not None:
            env["CLAUDE_PROJECT_DIR"] = project_dir
        if stdin_text is None:
            payload = {"tool_input": {"command": command}}
            payload.update(extra or {})
            stdin_text = json.dumps(payload)
        return subprocess.run(
            [sys.executable, HOOK_PATH],
            input=stdin_text,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_warns_in_godot_root(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "project.godot"), "w").close()
            proc = self.run_hook("dotnet build x.sln", d)
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertIn("additionalContext", out)
        self.assertNotIn("permissionDecision", out)

    def test_warns_in_subdirectory(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "godot"))
            open(os.path.join(d, "godot", "project.godot"), "w").close()
            proc = self.run_hook("dotnet build x.sln", d)
        self.assertIn("additionalContext", proc.stdout)

    def test_ignored_without_project_godot(self):
        with tempfile.TemporaryDirectory() as d:
            proc = self.run_hook("dotnet build x.sln", d)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_two_levels_down_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "a", "b"))
            open(os.path.join(d, "a", "b", "project.godot"), "w").close()
            proc = self.run_hook("dotnet build x.sln", d)
        self.assertEqual(proc.stdout, "")

    def test_cwd_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "project.godot"), "w").close()
            proc = self.run_hook("dotnet build x.sln", None, extra={"cwd": d})
        self.assertIn("additionalContext", proc.stdout)

    def test_all_flags_silent(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "project.godot"), "w").close()
            proc = self.run_hook(f"dotnet build x.sln {FULL}", d)
        self.assertEqual(proc.stdout, "")

    def test_bad_input_silent(self):
        for text in ("", "not json", "[]", '{"tool_input": null}', '{"tool_input": {"command": 3}}'):
            proc = self.run_hook(None, "/tmp", stdin_text=text)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
