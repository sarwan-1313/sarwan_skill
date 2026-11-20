#!/usr/bin/env python3
"""What real open-source projects decided about AI-assisted contributions.

  python3 policy_stats.py                     summary with examples
  python3 policy_stats.py --list no           every project in a group, with links (no, yes, with-conditions)

Reads data/policy-stats.json (from the CC0 open-source AI contribution policies list). No network calls.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "policy-stats.json"
GROUPS = [("no", "Do not accept AI-assisted contributions"), ("yes", "Accept them"),
          ("with-conditions", "Accept them only with extra conditions")]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="policy_stats.py")
    ap.add_argument("--list", choices=[g for g, _ in GROUPS], help="list every project in one group")
    args = ap.parse_args(argv)
    d = json.loads(DATA.read_text(encoding="utf-8"))

    if args.list:
        for e in d["examples"].get(args.list, []):
            print(f"{e['project']}: {e['policy_url'] or '(no link)'}")
        return 0

    total = d["total"]
    print(f"What {total} open-source projects with a published AI policy decided")
    print(f"(source: {d['source']}, {d['license']}, snapshot {d['snapshot']})\n")
    for key, label in GROUPS:
        n = d["counts"].get(key, 0)
        names = ", ".join(e["project"] for e in d["examples"].get(key, [])[:6])
        print(f"  {label:<44} {n:>4}  ({round(n * 100 / total)}%)  e.g. {names}")
    a = d["accepting"]
    print(f"\nOf the {a['total']} that accept AI help:")
    print(f"  require disclosure:              {a['disclosure_required']}")
    print(f"  require a person in the loop:    {a['human_in_the_loop']}")
    print("\nCareful: this list is made of projects that chose to publish a policy, and it over-represents bans.")
    for c in d["context"]:
        print(f"- {c['text']} ({c['source']})")
    print("\nRules worth deciding: how to disclose (Assisted-by trailer, PR description, checkbox); issue first;"
          "\nno pull requests from unsupervised agents; human-written descriptions and comments; security reports;"
          "\ngood first issues kept for people learning the project.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
