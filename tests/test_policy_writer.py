"""Tests for the ai-policy-writer skill, including round trips through the sarwan-skill checker."""
from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRITER = ROOT / "skills" / "ai-policy-writer"
sys.path.insert(0, str(WRITER / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "sarwan-skill" / "scripts"))
import check  # noqa: E402
import policy_block  # noqa: E402
import policy_stats  # noqa: E402

ALLOW = {"ai-assistance": "allowed", "disclosure": "assisted-by", "issue-first": "yes", "agent-opened-prs": "no",
         "human-written-text": "no"}
NOT_ACCEPTED = dict(ALLOW, **{"ai-assistance": "not-accepted", "disclosure": "not-needed", "issue-first": "no"})


def template(letter):
    """The prose of template A, B or C from assets/templates.md, with every optional [part] kept."""
    text = (WRITER / "assets" / "templates.md").read_text(encoding="utf-8")
    section = re.search(rf"^## {letter}\..*?```markdown\n(.*?)```", text, re.S | re.M).group(1)
    return re.sub(r"\[([^\]]*)\]", lambda m: m.group(1).split(" / ")[0], section)


def run(fn, argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = fn(argv)
    return code, out.getvalue()


class StatsTests(unittest.TestCase):
    def test_numbers_add_up(self):
        d = json.loads((WRITER / "data" / "policy-stats.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(d["counts"].values()), d["total"])
        self.assertEqual(d["accepting"]["total"], d["counts"].get("yes", 0) + d["counts"].get("with-conditions", 0))
        self.assertEqual(sum(len(v) for v in d["examples"].values()), d["total"])

    def test_summary_and_list(self):
        code, out = run(policy_stats.main, [])
        self.assertEqual(code, 0)
        self.assertIn("over-represents bans", out)
        code, out = run(policy_stats.main, ["--list", "no"])
        self.assertIn("QEMU", out)


class BlockTests(unittest.TestCase):
    def test_same_spec_as_the_checker(self):
        self.assertEqual(policy_block.SPEC, check.SPEC)

    def test_make_then_parse_with_the_checker(self):
        code, block = run(policy_block.main, ["make", *sum(([f"--{k}", v] for k, v in ALLOW.items()), [])])
        self.assertEqual(code, 0)
        values, problems = check.parse_block(block)
        self.assertEqual(problems, [])
        self.assertEqual({k: values[k] for k in ALLOW}, ALLOW)

    def test_check_files(self):
        d = Path(tempfile.mkdtemp())
        try:
            good, bad, none = d / "good.md", d / "bad.md", d / "none.md"
            good.write_text(policy_block.make(ALLOW), encoding="utf-8")
            bad.write_text("```ai-contribution-policy\nai-assistance: maybe\n```\n", encoding="utf-8")
            none.write_text("# Contributing\n", encoding="utf-8")
            self.assertEqual(run(policy_block.main, ["check", str(good)])[0], 0)
            code, out = run(policy_block.main, ["check", str(bad), str(none)])
            self.assertEqual(code, 1)
            self.assertIn("not one of", out)
            self.assertIn("no ai-contribution-policy block", out)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_not_accepted_with_disclosure_is_a_problem(self):
        _, problems = policy_block.parse(policy_block.make(dict(NOT_ACCEPTED, disclosure="assisted-by")))
        self.assertTrue(any("not-needed" in p for p in problems))


class RoundTripTests(unittest.TestCase):
    """What the writer produces must read the same way to the contributor-side checker."""

    def policy(self, contributing):
        d = Path(tempfile.mkdtemp())
        try:
            (d / "CONTRIBUTING.md").write_text(contributing, encoding="utf-8")
            findings, p, _ = check.policy_findings(d)
            return p, {f.code for f in findings}
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_template_a_reads_as_accepted_with_disclosure(self):
        p, codes = self.policy(template("A"))
        self.assertIn(p["stance"], ("disclose", "restricted"))
        p, codes = self.policy(template("A") + "\n" + policy_block.make(ALLOW))
        self.assertEqual(p["stance"], "disclose")
        self.assertEqual(p["disclosure"], "assisted-by")
        self.assertNotIn("policy-mismatch", codes)

    def test_template_c_reads_as_not_accepted(self):
        p, _ = self.policy(template("C"))
        self.assertEqual(p["stance"], "not-accepted")
        p, codes = self.policy(template("C") + "\n" + policy_block.make(NOT_ACCEPTED))
        self.assertEqual(p["stance"], "not-accepted")
        self.assertNotIn("policy-mismatch", codes)

    def test_template_b_with_its_block(self):
        p, codes = self.policy(template("B") + "\n" + policy_block.make(dict(ALLOW, **{"ai-assistance": "ask-first"})))
        self.assertEqual(p["stance"], "ask-first")
        self.assertNotIn("policy-mismatch", codes)

    def test_prose_and_block_that_disagree_are_flagged(self):
        _, codes = self.policy(template("C") + "\n" + policy_block.make(ALLOW))
        self.assertIn("policy-mismatch", codes)


if __name__ == "__main__":
    unittest.main()
