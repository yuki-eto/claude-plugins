import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("title_prefix.py")


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class TitlePrefixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name).resolve()
        cls.repo = root / "my-repo"
        cls.repo.mkdir()
        git("init", "-q", cwd=cls.repo)
        git("-c", "user.name=t", "-c", "user.email=t@example.com",
            "commit", "-q", "--allow-empty", "-m", "init", cwd=cls.repo)
        (cls.repo / "sub").mkdir()
        cls.worktree = root / "wt-elsewhere"
        git("worktree", "add", "-q", str(cls.worktree), cwd=cls.repo)
        cls.outside = root / "plain"
        cls.outside.mkdir()
        cls.scratch = root / "scratch-workspaces" / "abc"
        cls.scratch.mkdir(parents=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_hook(self, payload, env=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, **(env or {})},
        )
        self.assertEqual(result.returncode, 0)
        if not result.stdout.strip():
            return None
        out = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "UserPromptSubmit")
        return out["sessionTitle"]

    def title(self, cwd, prompt="ログインを直して", session_title=None):
        payload = {"hook_event_name": "UserPromptSubmit", "cwd": str(cwd), "prompt": prompt}
        if session_title is not None:
            payload["session_title"] = session_title
        return self.run_hook(payload)

    def test_repo_root(self):
        self.assertEqual(self.title(self.repo), "[my-repo] ログインを直して")

    def test_repo_subdir(self):
        self.assertEqual(self.title(self.repo / "sub"), "[my-repo] ログインを直して")

    def test_worktree_uses_main_repo_name(self):
        self.assertEqual(self.title(self.worktree), "[my-repo] ログインを直して")

    def test_outside_repo_is_global(self):
        self.assertEqual(self.title(self.outside), "[global] ログインを直して")

    def test_scratch_workspace_is_global(self):
        self.assertEqual(self.title(self.scratch), "[global] ログインを直して")

    def test_missing_cwd_is_global(self):
        self.assertEqual(self.title(""), "[global] ログインを直して")

    def test_long_prompt_is_truncated_to_first_line(self):
        prompt = "\n  " + "あ" * 50 + "\n二行目"
        self.assertEqual(self.title(self.repo, prompt), "[my-repo] " + "あ" * 40 + "…")

    def test_empty_prompt(self):
        self.assertEqual(self.title(self.repo, "   "), "[my-repo]")

    def test_existing_title_gets_prefix(self):
        self.assertEqual(self.title(self.repo, session_title="認証の改修"), "[my-repo] 認証の改修")

    def test_already_prefixed_title_is_left_alone(self):
        self.assertIsNone(self.title(self.repo, session_title="[my-repo] 認証の改修"))
        self.assertIsNone(self.title(self.repo, session_title="[my-repo]"))

    def test_other_leading_tag_is_replaced(self):
        self.assertEqual(self.title(self.repo, session_title="[global] 認証の改修"), "[my-repo] 認証の改修")

    def test_disable_env(self):
        payload = {"cwd": str(self.repo), "prompt": "x"}
        self.assertIsNone(self.run_hook(payload, env={"SESSION_TITLE_DISABLE": "1"}))

    def test_invalid_input_is_fail_open(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], input="not json",
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
