#!/usr/bin/env python3
"""Make or check an ai-contribution-policy block.

  python3 policy_block.py make --ai-assistance allowed --disclosure assisted-by --issue-first yes \\
                               --agent-opened-prs no --human-written-text no [--details URL]
  python3 policy_block.py check CONTRIBUTING.md [more files...]

`make` prints a valid block to paste into CONTRIBUTING.md. `check` finds the block in each file and
reports every problem. Exit code 0 when all is well, 1 otherwise. Python 3.9+, standard library only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Keep in step with SPEC in the sarwan-skill checker (a test makes sure they match).
SPEC = {
    "version": None,
    "ai-assistance": {"allowed", "ask-first", "not-accepted"},
    "disclosure": {"assisted-by", "pr-description", "both", "not-needed"},
    "issue-first": {"yes", "no"},
    "agent-opened-prs": {"yes", "no"},
    "human-written-text": {"yes", "no"},
    "details": None,
}
HINTS = {
    "ai-assistance": "allowed | ask-first | not-accepted",
    "disclosure": "assisted-by | pr-description | both | not-needed",
    "issue-first": "yes = only work on an issue a maintainer has accepted",
    "agent-opened-prs": "no = a person must review and open every pull request",
    "human-written-text": "yes = PR descriptions, issues and comments must be written by a person",
}
BLOCK = re.compile(r"^[ \t]*(```|~~~)[ \t]*ai-contribution-policy[ \t]*\n(.*?)^[ \t]*\1[ \t]*$", re.M | re.S)
REQUIRED = ("ai-assistance", "disclosure", "issue-first", "agent-opened-prs", "human-written-text")


def make(values):
    lines = ["```ai-contribution-policy", "version: 1"]
    for key in REQUIRED:
        lines.append(f"{key}: {values[key]}".ljust(32) + f"# {HINTS[key]}")
    if values.get("details"):
        lines.append(f"details: {values['details']}")
    lines.append("```")
    return "\n".join(lines) + "\n"


def parse(text):
    m = BLOCK.search(text)
    if not m:
        return None, ["no ai-contribution-policy block found"]
    values, problems = {}, []
    for raw in m.group(2).splitlines():
        line = re.split(r"\s#", raw, maxsplit=1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            problems.append(f"not a key: value line: {line}")
            continue
        key, value = (s.strip() for s in line.split(":", 1))
        key = key.lower()
        if key not in SPEC:
            problems.append(f"unknown key: {key}")
            continue
        if SPEC[key] is not None and value.lower() not in SPEC[key]:
            problems.append(f"{key}: '{value}' is not one of {', '.join(sorted(SPEC[key]))}")
            continue
        values[key] = value if SPEC[key] is None else value.lower()
    missing = [k for k in REQUIRED if k not in values]
    if missing:
        problems.append("missing: " + ", ".join(missing))
    if values.get("ai-assistance") == "not-accepted" and values.get("disclosure") not in (None, "not-needed"):
        problems.append("ai-assistance is not-accepted, so disclosure should be not-needed")
    return values, problems


def main(argv=None):
    ap = argparse.ArgumentParser(prog="policy_block.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make")
    for key in REQUIRED:
        mk.add_argument(f"--{key}", required=True, choices=sorted(SPEC[key]))
    mk.add_argument("--details", help="link to the full policy, if it lives elsewhere")
    ck = sub.add_parser("check")
    ck.add_argument("files", nargs="+")
    args = ap.parse_args(argv)

    if args.cmd == "make":
        values = {k: getattr(args, k.replace("-", "_")) for k in REQUIRED}
        values["details"] = args.details
        block = make(values)
        _, problems = parse(block)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        print(block, end="")
        return 0

    status = 0
    for name in args.files:
        try:
            values, problems = parse(Path(name).read_text(encoding="utf-8", errors="replace"))
        except OSError as e:
            values, problems = None, [str(e)]
        if problems:
            status = 1
            print(f"{name}: " + "; ".join(problems))
        else:
            print(f"{name}: ok ({', '.join(f'{k}: {v}' for k, v in values.items())})")
    return status


if __name__ == "__main__":
    sys.exit(main())
