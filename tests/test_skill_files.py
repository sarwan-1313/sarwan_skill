"""Checks that the skill, plugin and data files stay valid and consistent."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "sarwan-skill"
SKILL_DIRS = sorted(p for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").exists())


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, "SKILL.md must start with YAML frontmatter"
    fields = {}
    for line in m.group(1).splitlines():
        if re.match(r"^[a-z-]+:", line):
            key, value = line.split(":", 1)
            fields[key] = value.strip()
    return fields, m.group(2)


class SkillFileTests(unittest.TestCase):
    def skills(self):
        self.assertEqual([p.name for p in SKILL_DIRS], ["ai-policy-writer", "sarwan-skill"])
        for d in SKILL_DIRS:
            fields, body = frontmatter((d / "SKILL.md").read_text(encoding="utf-8"))
            yield d, fields, body

    def test_name_follows_agent_skills_spec(self):
        for d, fields, _ in self.skills():
            with self.subTest(skill=d.name):
                self.assertRegex(fields["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
                self.assertLessEqual(len(fields["name"]), 64)
                self.assertEqual(fields["name"], d.name)

    def test_description(self):
        for d, fields, _ in self.skills():
            with self.subTest(skill=d.name):
                self.assertTrue(0 < len(fields["description"]) <= 1024, len(fields["description"]))

    def test_body_is_short(self):
        for d, _, body in self.skills():
            with self.subTest(skill=d.name):
                self.assertLess(len(body.splitlines()), 120)
                self.assertLess(len(body.split()), 1300)

    def test_files_referenced_exist(self):
        for d, _, body in self.skills():
            for ref in set(re.findall(r"(?:\.\./[\w-]+/)?(?:scripts|assets)/[\w.-]+", body)):
                with self.subTest(skill=d.name, ref=ref):
                    self.assertTrue((d / ref).exists(), ref)


class PluginFileTests(unittest.TestCase):
    def test_plugin_and_marketplace_agree(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        entry = market["plugins"][0]
        self.assertEqual(plugin["name"], entry["name"])
        self.assertEqual(plugin["version"], entry["version"])
        self.assertEqual(sorted(Path(p).name for p in plugin["skills"]), [d.name for d in SKILL_DIRS])
        for path in plugin["skills"]:
            self.assertTrue((ROOT / path / "SKILL.md").exists(), path)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"/plugin install {entry['name']}@{market['name']}", readme)


class DataFileTests(unittest.TestCase):
    def test_known_policies(self):
        data = json.loads((SKILL_DIR / "data" / "known-policies.json").read_text(encoding="utf-8"))
        self.assertEqual(data["license"], "CC0-1.0")
        self.assertGreater(len(data["entries"]), 100)
        for e in data["entries"]:
            self.assertIn(e["ai_allowed"], {"yes", "no", "with-conditions", "unclear"}, e["project"])
            for key in e["repos"]:
                self.assertRegex(key, r"^[a-z0-9.-]+/[^\s]+$", e["project"])


if __name__ == "__main__":
    unittest.main()
