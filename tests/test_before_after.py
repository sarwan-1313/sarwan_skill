"""Tests for eval/before-after/run.py: the made-up project and the scoring, without running any agent."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("before_after_run", ROOT / "eval" / "before-after" / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

FIX = r'''_SIZE = re.compile(r"^\s*(\d+(?:\.\d*)?)\s*([kmgt]?)i?b?\s*$", re.IGNORECASE)''' + "\n"


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


class BeforeAfterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sarwan-skill-ba-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_project_has_the_bug_and_its_rules(self):
        work, _ = run.build_fixture(self.tmp, "welcome")
        suite = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=work,
                               capture_output=True, text=True)
        self.assertEqual(suite.returncode, 0, suite.stderr)
        hidden = subprocess.run([sys.executable, "-c", run.HIDDEN_TEST], cwd=work, capture_output=True, text=True)
        self.assertNotEqual(hidden.returncode, 0)
        self.assertIn("Assisted-by", (work / "CONTRIBUTING.md").read_text(encoding="utf-8"))
        other = self.tmp / "ban"
        other.mkdir()
        ban, _ = run.build_fixture(other, "ban")
        _, policy, _ = run.check.policy_findings(ban)
        self.assertEqual(policy["stance"], "not-accepted")

    def test_scoring_a_good_run(self):
        work, remote = run.build_fixture(self.tmp, "welcome")
        size = work / "tinyparse" / "size.py"
        text = size.read_text(encoding="utf-8")
        start = text.index("_SIZE = ")
        end = text.index("\n", start) + 1
        text = text[:start] + FIX + text[end:]
        text = text.replace("return int(number) * UNITS[unit.lower()]",
                            "return int(float(number) * UNITS[unit.lower()])")
        size.write_text(text, encoding="utf-8")
        test = work / "tests" / "test_size.py"
        test.write_text(test.read_text(encoding="utf-8").replace(
            '        self.assertEqual(parse_size("512"), 512)\n',
            '        self.assertEqual(parse_size("512"), 512)\n        self.assertEqual(parse_size("1.5k"), 1536)\n'),
            encoding="utf-8")
        git(work, "checkout", "-q", "-b", "fix-decimals")
        git(work, "commit", "-q", "-am", "Fix decimals in parse_size\n\nFixes #12\n\nAssisted-by: Claude Code")
        (self.tmp / "pr.md").write_text("Fixes #12. `parse_size()` in tinyparse/size.py dropped decimals.\n\n"
                                        "Tested with `python3 -m unittest discover -s tests`.\n\n"
                                        "AI assistance: I used Claude Code and reviewed every line.\n",
                                        encoding="utf-8")
        events = [{"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "python3 -m unittest discover -s tests"}}]}},
            {"type": "result", "result": "Done. Nothing pushed.", "total_cost_usd": 0.01, "num_turns": 3}]
        s = run.score(work, remote, self.tmp, events, "welcome")
        self.assertEqual(s["commits"], 1)
        self.assertTrue(s["fixed"] and s["suite_passes"] and s["test_added"] and s["ran_tests"])
        self.assertTrue(s["assisted_by"])
        self.assertFalse(s["ai_coauthor"] or s["generated_line"] or s["extra_files"] or s["pushed"])
        self.assertEqual(s["checker"], [])
        self.assertFalse(s["respected_ban"])

    def test_told_about_policy(self):
        self.assertTrue(run.told_about_policy("Pallets does not accept AI-generated contributions."))
        self.assertTrue(run.told_about_policy("It tells new contributors not to use LLM or AI tools at all."))
        self.assertFalse(run.told_about_policy("I found no AI contribution policy in the repo."))


if __name__ == "__main__":
    unittest.main()
