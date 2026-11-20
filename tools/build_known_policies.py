#!/usr/bin/env python3
"""Rebuild skills/sarwan-skill/data/known-policies.json from the CC0 list at
https://github.com/melissawm/open-source-ai-contribution-policies

Usage: python3 tools/build_known_policies.py path/to/that/README.md [snapshot-date]

Many listed projects host their policy on a website, so the list gives no
repository for them. ALIASES below maps those projects to their main
repositories (or a whole organisation, written owner/*) so the checker can
still find them. Only add an alias when you are sure it is the project's
canonical repository.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "skills" / "sarwan-skill" / "data" / "known-policies.json"
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
GITHUB_LIKE = {"github.com", "codeberg.org", "bitbucket.org", "gitea.com"}

ALIASES = {
    "Apache DataFusion": ["github.com/apache/datafusion"],
    "Apache Kvrocks": ["github.com/apache/kvrocks"],
    "Apache® Software Foundation (ASF)": ["github.com/apache/*"],
    "Arrow": ["github.com/apache/arrow"],
    "Asahi Linux": ["github.com/asahilinux/*"],
    "Bevy": ["github.com/bevyengine/bevy"],
    "chezmoi": ["github.com/twpayne/chezmoi"],
    "Clojure": ["github.com/clojure/clojure"],
    "CuPy": ["github.com/cupy/cupy"],
    "curl": ["github.com/curl/curl"],
    "Django": ["github.com/django/django"],
    "EasyBuild": ["github.com/easybuilders/*"],
    "Elementary OS": ["github.com/elementary/*"],
    "Exim": ["github.com/exim/exim"],
    "FastAPI": ["github.com/fastapi/fastapi"],
    "GDAL": ["github.com/osgeo/gdal"],
    "Gentoo Linux": ["github.com/gentoo/*"],
    "Godot Engine": ["github.com/godotengine/godot"],
    "Icechunk": ["github.com/earth-mover/icechunk"],
    "Inkscape": ["gitlab.com/inkscape/inkscape"],
    "IREE (Intermediate Representation Execution Environment)": ["github.com/iree-org/iree"],
    "Jellyfin": ["github.com/jellyfin/*"],
    "Joomla": ["github.com/joomla/joomla-cms"],
    "Kubernetes": ["github.com/kubernetes/*"],
    "Linux Kernel": ["github.com/torvalds/linux"],
    "LLVM": ["github.com/llvm/llvm-project"],
    "Matplotlib": ["github.com/matplotlib/matplotlib"],
    "napari": ["github.com/napari/napari"],
    "NetBSD": ["github.com/netbsd/src"],
    "NumPy": ["github.com/numpy/numpy"],
    "OpenJDK": ["github.com/openjdk/*"],
    "Oxide": ["github.com/oxidecomputer/*"],
    "Pallets": ["github.com/pallets/*"],
    "Pandas": ["github.com/pandas-dev/pandas"],
    "pretix": ["github.com/pretix/pretix"],
    "QEMU": ["github.com/qemu/qemu", "gitlab.com/qemu-project/qemu"],
    "Rust": ["github.com/rust-lang/*"],
    "scikit-image": ["github.com/scikit-image/scikit-image"],
    "scikit-learn": ["github.com/scikit-learn/scikit-learn"],
    "SciPy": ["github.com/scipy/scipy"],
    "Servo": ["github.com/servo/servo"],
    "SymPy": ["github.com/sympy/sympy"],
    "Telegraf": ["github.com/influxdata/telegraf"],
    "Twisted": ["github.com/twisted/twisted"],
    "typescript-eslint": ["github.com/typescript-eslint/typescript-eslint"],
    "Unbound": ["github.com/nlnetlabs/unbound"],
    "Wagtail": ["github.com/wagtail/wagtail"],
    "Zig": ["github.com/ziglang/zig", "codeberg.org/ziglang/zig"],
}


def repo_key(url: str) -> str | None:
    """host/owner/repo key for a forge URL (GitHub, GitLab, Gitea/Forgejo), or None for websites."""
    m = re.match(r"https?://(?:www\.)?([^/]+)/([^?#]+)", url.strip())
    if not m:
        return None
    host, path = m.group(1).lower(), m.group(2)
    parts = [p for p in path.split("/") if p]
    if "/-/" in path or host.startswith("gitlab."):  # GitLab, possibly nested groups
        parts = [p for p in path.split("/-/")[0].split("/") if p]
    elif host in GITHUB_LIKE or "/src/branch/" in path or "/src/commit/" in path:
        parts = parts[:2]  # GitHub-style or Gitea/Forgejo
    else:
        return None
    if len(parts) < 2:
        return None
    key = f"{host}/{'/'.join(parts)}".lower()
    return key[:-4] if key.endswith(".git") else key


def stance(value: str) -> str:
    v = value.strip().lower()
    if v.endswith("*"):
        return "with-conditions"
    return {"yes": "yes", "no": "no"}.get(v, "unclear")


def main() -> None:
    src = Path(sys.argv[1]).read_text(encoding="utf-8")
    snapshot = sys.argv[2] if len(sys.argv) > 2 else "unknown"
    entries, used_aliases = [], set()
    for line in src.splitlines():
        if not line.startswith("[") or line.count("|") < 6:
            continue
        cells = [c.strip() for c in line.split("|")]
        project_links = LINK.findall(cells[0])
        if not project_links:
            continue
        name, homepage = project_links[0]
        name = name.strip()
        policy_links = LINK.findall(cells[1])
        policy_url = policy_links[0][1] if policy_links else ""
        keys = {k for k in (repo_key(homepage), repo_key(policy_url)) if k}
        if name in ALIASES:
            keys.update(ALIASES[name])
            used_aliases.add(name)
        notes = re.sub(r"\s+", " ", LINK.sub(r"\1", cells[6] if len(cells) > 6 else "")).strip(" -")
        entries.append({
            "project": name,
            "homepage": homepage,
            "policy_url": policy_url,
            "repos": sorted(keys),
            "ai_allowed": stance(cells[2]),
            "disclosure_required": stance(cells[3]),
            "human_in_the_loop": stance(cells[5]),
            "notes": notes[:300],
        })
    missing = sorted(set(ALIASES) - used_aliases)
    if missing:
        print("warning: aliases for projects no longer in the list:", ", ".join(missing))
    data = {
        "source": "https://github.com/melissawm/open-source-ai-contribution-policies",
        "license": "CC0-1.0",
        "snapshot": snapshot,
        "aliases": "Repository aliases for projects whose policy lives on a website were added by sarwan_skill (tools/build_known_policies.py).",
        "caution": "The source list says its classification is a general guide, not the source of truth. Always read the policy itself.",
        "entries": entries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    with_repo = sum(1 for e in entries if e["repos"])
    print(f"wrote {len(entries)} entries ({with_repo} matchable by repository) to {OUT}")
    write_stats(entries, snapshot)


# Well-known projects to show first as examples. Everything else follows alphabetically.
NOTABLE = ["Linux Kernel", "LLVM", "curl", "Django", "NumPy", "Kubernetes", "Rust", "Fedora", "pip", "pytest",
           "Ghostty", "SciPy", "Matplotlib", "QEMU", "Gentoo Linux", "Zig", "Servo", "NetBSD", "Pallets", "Bevy",
           "OpenJDK", "Godot Engine", "Asahi Linux", "Alacritty", "llama.cpp", "Apache Airflow", "Homebrew"]
STATS_OUT = OUT.parent.parent.parent / "ai-policy-writer" / "data" / "policy-stats.json"


def write_stats(entries, snapshot):
    """A small summary for the ai-policy-writer skill, so it does not need the full list."""
    def rank(e):
        return (NOTABLE.index(e["project"]) if e["project"] in NOTABLE else len(NOTABLE), e["project"].lower())

    groups = {}
    for e in sorted(entries, key=rank):
        groups.setdefault(e["ai_allowed"], []).append({"project": e["project"], "policy_url": e["policy_url"]})
    accepting = [e for e in entries if e["ai_allowed"] in ("yes", "with-conditions")]
    stats = {
        "source": "https://github.com/melissawm/open-source-ai-contribution-policies",
        "license": "CC0-1.0",
        "snapshot": snapshot,
        "total": len(entries),
        "counts": {k: len(v) for k, v in groups.items()},
        "accepting": {
            "total": len(accepting),
            "disclosure_required": sum(1 for e in accepting if e["disclosure_required"] == "yes"),
            "human_in_the_loop": sum(1 for e in accepting if e["human_in_the_loop"] == "yes"),
        },
        "examples": groups,
        "context": [
            {"text": "Of 1,000 popular GitHub repositories, 118 had an AI contribution policy. Of those, 78% accept "
                     "AI-assisted contributions and 22% discourage them; 51% require disclosure and 74% require "
                     "human oversight.",
             "source": "Hora and Robbes, 'AI Policy, Disclosure, and Human in the Loop', arXiv:2605.16706 (2026)"},
            {"text": "Maintainers estimate that about 25% of incoming pull requests are low-quality AI output "
                     "(31% at large projects).",
             "source": "Linux Foundation Research, October 2026"},
        ],
    }
    STATS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATS_OUT.write_text(json.dumps(stats, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote policy statistics to {STATS_OUT}")


if __name__ == "__main__":
    main()
