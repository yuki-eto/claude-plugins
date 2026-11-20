import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("session_context.py")
AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"


class SessionContextTest(unittest.TestCase):
    def run_hook(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input='{"hook_event_name": "SessionStart", "source": "startup"}',
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0)
        return json.loads(result.stdout)

    def test_outputs_session_start_context(self):
        out = self.run_hook()["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")
        self.assertTrue(out["additionalContext"].startswith("[model-routing]"))

    def test_mentions_every_agent_by_full_name(self):
        context = self.run_hook()["hookSpecificOutput"]["additionalContext"]
        agents = sorted(p.stem for p in AGENTS_DIR.glob("*.md"))
        self.assertTrue(agents)
        for name in agents:
            self.assertIn(f"model-routing:{name}", context)


if __name__ == "__main__":
    unittest.main()
