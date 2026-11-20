#!/usr/bin/env python3
"""Score the policy reader against real projects' published AI policies.

  python3 eval/run.py [--cache DIR] [--set tuning|round1|round2]

For each project in eval/projects.tsv it fetches only the documentation files
(a sparse, blob-less git clone), reads the policy WITHOUT the known-policies
list, and compares the result with the label from the public list:

  list says "no"   -> right if the reader says not-accepted
  list says "yes"  -> right if the reader says accepted (allowed, disclose or restricted)
  "unclear"/"silent" counts as a miss: the checker then tells the agent to ask.

Needs git and network access to github.com. The cache makes re-runs fast.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "sarwan-skill" / "scripts"))
import check  # noqa: E402

PATTERNS = ["/*.md", "/*.rst", "/*.txt", "/*.adoc", "/CONTRIBUTING*", "/HACKING*", "/AGENTS.md", "/.github/*.md",
            "/.github/PULL_REQUEST_TEMPLATE/", "/.github/ISSUE_TEMPLATE/", "/docs/*.md", "/docs/*.rst", "/doc/*.md",
            "/doc/*.rst", "/docs/devel/*.rst", "/doc/developers/*.rst", "/doc/source/dev/*.rst", "/docs/contributing/",
            "/contributing-docs/"]


def fetch(repo, extra, dest):
    if (dest / ".git").exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{repo}"
    run = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True, timeout=600)  # noqa: E731
    if run("clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout", url, str(dest)).returncode:
        return False
    run("-C", str(dest), "sparse-checkout", "init", "--no-cone")
    run("-C", str(dest), "sparse-checkout", "set", "--no-cone", *PATTERNS, *([f"/{extra}"] if extra else []))
    return run("-C", str(dest), "checkout", "-q").returncode == 0


def verdict(label, stance):
    if stance in ("silent", "unclear"):
        return "MISSED"
    if label == "no":
        return "OK" if stance == "not-accepted" else "WRONG"
    if label in ("yes", "with-conditions"):
        return "OK" if stance != "not-accepted" else "WRONG"
    return "OK"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "sarwan-skill-eval"))
    ap.add_argument("--set", choices=["tuning", "round1", "round2"])
    args = ap.parse_args()
    rows = [l.rstrip("\n").split("\t") for l in (ROOT / "eval" / "projects.tsv").read_text().splitlines()[1:]]
    totals = {}
    for set_name, repo, path, label in rows:
        if args.set and set_name != args.set:
            continue
        dest = Path(args.cache) / repo.replace("/", "__")
        if not fetch(repo, path, dest):
            print(f"{'SKIPPED':7s} {repo} (could not fetch)")
            continue
        stance = check.read_policy(dest)["stance"]
        v = verdict(label, stance)
        totals.setdefault(set_name, {}).setdefault(v, 0)
        totals[set_name][v] += 1
        print(f"{v:7s} {set_name:7s} {repo:45s} list={label:16s} reader={stance}")
    print()
    for set_name, t in totals.items():
        print(f"{set_name}: " + ", ".join(f"{k} {v}" for k, v in sorted(t.items())))


if __name__ == "__main__":
    main()
