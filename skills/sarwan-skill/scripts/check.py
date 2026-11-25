#!/usr/bin/env python3
"""sarwan_skill checker: read an open-source project's rules for AI-assisted
contributions, and check a contribution for the things maintainers reject.

  python3 check.py policy [--repo DIR]                 what the project allows
  python3 check.py diff   [--repo DIR] [--base REF]     your change, before you show it
  python3 check.py pr     FILE|- [--repo DIR]           a pull request description draft
  python3 check.py all    [--repo DIR] [--base REF] [--pr FILE]

Add --json for machine-readable output. Exit code: 0 nothing to fix,
1 something to fix, 2 stop (the project does not accept AI-assisted work).

Python 3.9+, standard library only. It reads files and runs git; it never
uses the network. It points at lines; a person decides what they mean.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KNOWN_POLICIES = HERE.parent / "data" / "known-policies.json"
LEVELS = ("stop", "fix", "check", "info")

# --------------------------------------------------------------------------
# Findings and output
# --------------------------------------------------------------------------


class Finding:
    def __init__(self, level, code, message, where="", quote=""):
        self.level, self.code, self.message, self.where, self.quote = level, code, message, where, quote

    def as_dict(self):
        d = {"level": self.level, "code": self.code, "message": self.message}
        if self.where:
            d["where"] = self.where
        if self.quote:
            d["quote"] = self.quote
        return d


def worst(findings):
    for level in LEVELS:
        if any(f.level == level for f in findings):
            return level
    return "info"


def print_section(title, findings):
    print(f"\n== {title}")
    if not findings:
        print("  ok     nothing found")
        return
    for f in sorted(findings, key=lambda f: LEVELS.index(f.level)):
        print(f"  {f.level.upper():<6} {f.message}")
        if f.where:
            print(f"         at {f.where}")
        if f.quote:
            print(f'         "{f.quote}"')


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def git(repo, *args):
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None
    return r.stdout if r.returncode == 0 else None


def read_text(path, limit=1_000_000):
    try:
        if path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def short(text, n=180):
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


SKIP_DIRS = {".git", "node_modules", "vendor", "third_party", "thirdparty", "external", "dist", "build",
             "target", ".venv", "venv", "env", "__pycache__", ".tox", ".nox", "site-packages", "deps",
             "out", ".next", "coverage", ".mypy_cache", ".pytest_cache", "bower_components"}


def walk(root, max_depth=4, max_files=20000):
    root = Path(root)
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        depth = 0 if str(rel) == "." else len(rel.parts)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not (depth >= max_depth)]
        for name in filenames:
            count += 1
            if count > max_files:
                return
            yield Path(dirpath) / name


def words(stem):
    """Split names like AI_POLICY, ai-tool-policy or AIToolPolicy into lowercase words."""
    return [w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", stem)]


# --------------------------------------------------------------------------
# Policy: finding the files
# --------------------------------------------------------------------------

DOC_EXT = {".md", ".markdown", ".rst", ".txt", ".adoc", ""}
CONTRIB_STEMS = {"contributing", "contribute", "contributors", "contribution", "contributions", "developing",
                 "development", "hacking", "contributor-guide", "contributing-guide", "code-provenance"}
AGENT_FILES = {"agents.md", "claude.md", "gemini.md", "copilot-instructions.md", ".cursorrules", ".windsurfrules"}


def classify_file(rel: Path):
    """Return the kind of policy-relevant file this is, or None."""
    name, stem, ext = rel.name.lower(), rel.stem.lower(), rel.suffix.lower()
    parent = [p.lower() for p in rel.parts[:-1]]
    if name in AGENT_FILES:
        return "agents"
    if "issue_template" in parent and ext in {".md", ".yml", ".yaml"}:
        return "template"
    if ext not in DOC_EXT:
        return None
    w = set(words(rel.stem))
    if w & {"ai", "llm", "llms", "genai", "generative"} and w & {
            "policy", "policies", "guideline", "guidelines", "contribution", "contributions", "contributing", "usage",
            "use", "rules", "covenant", "charter", "principles", "statement", "ethics", "guide"}:
        return "ai-policy"
    if set(parent) & {"contributing.d", "contributing-docs", "contributing", "contribute", "contributor-guide"}:
        return "contributing"
    if stem in CONTRIB_STEMS:
        return "contributing"
    if "pull_request_template" in name or "merge_request_templates" in parent or "pull_request_template" in parent:
        return "template"
    if len(rel.parts) == 1 and stem == "readme":
        return "readme"
    return None


def candidate_files(repo):
    found = []
    for path in walk(repo):
        rel = path.relative_to(repo)
        kind = classify_file(rel)
        if kind:
            found.append((kind, rel))
    order = {"ai-policy": 0, "contributing": 1, "agents": 2, "template": 3, "readme": 4}
    return sorted(found, key=lambda kr: (order[kr[0]], len(kr[1].parts), str(kr[1])))


# --------------------------------------------------------------------------
# Policy: reading the rules
# --------------------------------------------------------------------------

AI_TERM = re.compile(
    r"\bAI\b|\bA\.I\.|\bLLMs?\b|\bGenAI\b|(?i:\bgen(?:erative)?[- ]?AI\b|large[- ]language[- ]models?|"
    r"\blanguage[- ]models?\b|\bartificial[- ]intelligence\b|\bchatgpt\b|\bcopilot\b|\bclaude\b|machine[- ]generated|"
    r"\bcoding[- ](?:assistant|agent)s?\b|\bvibe[- ]?cod\w*|\bslop\b)")
POLICY_WORD = re.compile(r"(?i)generat|assist|written|\btools?\b|disclos|accept|allow|polic|slop|agent|"
                         r"permit|prohibit|forbid|\bban|contribut|pull request|\bPRs?\b|patch|submi")
POLICY_HEADING = re.compile(r"(?i)polic|contribut|guideline|usage|\buse of\b|\brules?\b|generated|assisted|slop")
T = (r"(?:\bAI\b|\bLLMs?\b|\bgenerative\b|\bmachine[- ]generated\b|\bChatGPT\b|\bCopilot\b|\blanguage models?\b|"
     r"\bGenAI\b|\bartificial intelligence\b)")
CHECKBOX = re.compile(r"^\s*(?:[-*+]\s*)?\[\s?[xX ]?\s?\]")
NEGATION = re.compile(r"(?i)\b(?:no|not|never|without|none|didn't|haven't|wasn't|weren't)\b")

# Patterns are only tried on paragraphs that are already about AI.
NOT_WORD = r"(?!not\b|never\b|no\b)"
SIGNALS = {
    "ban": [
        r"(?i)\b(?:do|does|did|will|must|may|can|shall|should|have|has|had)\s*(?:not|n't)\s+(?:\w+\s+){0,2}?(?:accept|"
        r"allow|permit|merge|take|consider|review|used?|using|submit|send|open|include|incorporate|contain|contribute|"
        r"post|file)"
        r"(?:s|ed|ing)?\b[^.;:]{0,80}?" + T,
        r"(?i)\b(?:never|won't|cannot|can't)\s+(?:\w+\s+){0,2}?(?:accept|allow|permit|merge|take|consider)"
        r"(?:s|ed|ing)?\b[^.;:]{0,80}?" + T,
        r"(?i)" + T + r"[^.;:]{0,160}?\b(?:(?:is|are|will be)\s+(?:strictly\s+|expressly\s+|explicitly\s+)?(?:not\s+"
        r"(?:accepted|allowed|permitted|authorized|welcome|welcomed|tolerated|acceptable)|forbidden|prohibited|banned|"
        r"disallowed|rejected|unwelcome)|(?:will|shall|can|may)\s*(?:not|n't)\s+be\s+(?:accepted|allowed|permitted|"
        r"merged|considered|reviewed|tolerated))",
        r"(?i)\b(?:forbidden|prohibited|banned|not (?:allowed|permitted|accepted))\s+to\s+(?:\w+\s+){0,6}?" + T,
        r"(?i)\b(?:no|bans?(?:\s+on)?|banned|prohibits?|forbids?)\s+(?:\w+\s+){0,2}?" + T +
        r"(?!\s*(?:-\w+\s+)?(?:polic|guideline|rule|usage polic))(?!\s+(?:tools?\s+)?(?:were\s+|was\s+|is\s+|are\s+)?"
        r"used)",
        r"(?i)\bstrict(?:ly)?\s+no[- ](?:LLM|AI)\b",
        r"(?i)\b(?:AI|LLM)[- ]free\b",
        r"(?i)\b(?:refuse|reject|decline|close)\w*\b[^.;]{0,120}?" + T,
        r"(?i)" + T + r"[^.;]{0,80}?\b(?:will be|are|is|get)\s+(?:\w+\s+)?(?:closed|rejected|declined|refused)\b",
        r"(?i)\brefrain\w*\s+from\b[^.;]{0,120}?" + T,
        r"(?i)\b(?:must|should|may|can)\s*(?:not|n't)\s+be\s+(?:\w+\s+)?(?:generated|written|created|produced|made)"
        r"\s+(?:\w+\s+){0,2}?(?:by|with|using)\s+(?:\w+\s+){0,2}?" + T,
    ],
    "disclose": [
        r"(?i)\bdisclos\w*",
        r"\bAssisted-by\b",
        r"(?i)\bGenerated-by:",
        r"(?i)\btransparen\w*",
        r"(?i)\b(?:reveal|declare)\w*\b",
        r"(?i)\b(?:state|mention|indicate|label|mark|tell us|let us know|be upfront|be open)\w*\b[^.;:]{0,60}?"
        r"(?:" + T + r"|\btools?\b|\bused\b)",
    ],
    "allow": [
        r"(?i)" + T + r"[^.;:]{0,60}?\b(?:is|are)\s+(?:" + NOT_WORD + r"\w+\s+)?(?:allowed|permitted|welcome|welcomed|"
        r"fine|ok|okay|acceptable|encouraged)\b",
        r"(?i)\byou\s+(?:may|can|are free to|are welcome to)\s+(?:still\s+)?(?:use|submit|contribute)\b",
        r"(?i)(?<!not )(?<!n't )(?<!never )\b(?:accept|allow|permit|welcome)(?:s|ed)?\s+(?:\w+\s+){0,6}?" + T,
        r"(?i)\b(?:cannot|can't|will not|won't|do not|don't)\s+(?:\w+\s+){0,3}?(?:ban|police|forbid|prohibit)\b",
        r"(?i)" + T + r"[^.;:]{0,30}?\bcan be (?:very\s+)?(?:helpful|useful)\b",
        r"(?i)" + T + r"[^.;:]{0,40}?\b(?:may|can)\s+be\s+used\b",
        r"(?i)\bif\s+(?:you|you've|you have)\s+(?:used?|employ\w*|relied on)\s+(?:\w+\s+){0,2}?" + T,
    ],
}
SIGNALS = {k: [re.compile(p) for p in v] for k, v in SIGNALS.items()}

# What a rule is about decides how much it limits an agent that writes code.
CORE_SCOPE = re.compile(r"(?i)\bcode\b|\bpatch(?:es)?\b|pull requests?|\bPRs?\b|contribut\w*|submission|\bcommits?\b|"
                        r"merge requests?|\bchanges\b|implementation")
SCOPE_PHRASES = re.compile(r"(?i)(?:PR|pull request|merge request|commit)\s+(?:descriptions?|messages?|comments?|"
                           r"titles?|text|summar\w+)|code reviews?")
PARTIAL_SCOPE = re.compile(r"(?i)\bissues?\b|bug reports?|security reports?|\bcomments?\b|discussions?|communicat\w*|"
                           r"\bdescriptions?\b|\bmedia\b|\bimages?\b|artwork|\btranslat\w*|speak for you|\bmessages?\b|"
                           r"\bforums?\b|\bchat\b|good[- ]first|\breviews?\b")
AUTONOMY = re.compile(r"(?i)\bautonomously\b|unsupervised|unattended|without (?:a |any )?(?:human|person)|"
                      r"no (?:human|person) review\w*|fully[- ]automated\s+"
                      r"(?:agents?|bots?|PRs?|pull requests?)|agentic tools")
UNDERSTAND = r"(?:\w+\s+)?(?:understand|understood|explain|test|review|verif|read|check)\w*"
CONDITIONAL = re.compile(r"(?i)\bunless\b|\bundisclosed\b|\bwithout\s+(?:\w+\s+)?(?:disclos|review|understand|test|"
                         r"verif|human|explain)\w*|\b(?:you|that you)\s+(?:can't|cannot|don't|do not|haven't|have not|"
                         r"did not|didn't)\s+" + UNDERSTAND + r"|\bif you (?:can't|cannot|don't|do not)\s+" + UNDERSTAND)
MINOR_USE = re.compile(r"(?i)proofread|translat|grammar|spell|research|brainstorm|debug|static analysis|\bsearch|"
                       r"autocomplet|understand(?:ing)? (?:the )?(?:code|codebase)|\blearn")


EMPHASIS = re.compile(r"(?<!\w)[*_]+|[*_]+(?!\w)")  # markdown **bold** and _italic_ markers


def sentence_at(text, start, end):
    a = max(text.rfind(c, 0, start) for c in ".!?;") + 1
    ends = [i for i in (text.find(c, end) for c in ".!?;") if i != -1]
    return text[a:(min(ends) + 1 if ends else len(text))].strip()


def scan_signals(text):
    """Return the set of signals in a paragraph that is about AI.

    ban-core: AI help is not accepted for code or contributions.
    ban-partial: only some uses are not accepted (issues, communication, unsupervised agents, conditions).
    allow-strong / allow-minor: AI help is accepted (minor = only for proofreading, research and the like).
    disclose: AI help is accepted when disclosed.
    """
    text = EMPHASIS.sub("", text)
    found = set()
    for pat in SIGNALS["ban"]:
        for m in pat.finditer(text):
            s = sentence_at(text, m.start(), m.end())
            rest = SCOPE_PHRASES.sub(" ", s)
            partial = AUTONOMY.search(s) or CONDITIONAL.search(s) or (PARTIAL_SCOPE.search(rest) and
                                                                     not CORE_SCOPE.search(rest))
            found.add("ban-partial" if partial else "ban-core")
    for pat in SIGNALS["allow"]:
        for m in pat.finditer(text):
            found.add("allow-minor" if MINOR_USE.search(sentence_at(text, m.start(), m.end())) else "allow-strong")
    if any(p.search(text) for p in SIGNALS["disclose"]):
        found.add("disclose")
    return found


def decide_stance(signals, any_hits):
    core, partial = "ban-core" in signals, "ban-partial" in signals
    strong = bool(signals & {"allow-strong", "disclose"})
    if core and not strong:
        return "not-accepted"
    if core or partial or (signals == {"allow-minor"}):
        return "restricted"
    if "disclose" in signals:
        return "disclose"
    if "allow-strong" in signals:
        return "allowed"
    return "unclear" if any_hits else "silent"

FLAGS = {
    "issue-first": (r"(?i)\b(?:open|file|create|start with)\s+an?\s+(?:new\s+)?issue\s+(?:first|before)|"
                    r"\b(?:linked|accepted|approved|existing)\s+issue\b|\bdrive[- ]by\b|\bissue[- ]first\b",
                    "Wants an issue first: work only on an issue maintainers have accepted, and link it."),
    "human-review": (r"(?i)\b(?:review|understand|explain|test|verify)\w*\s+(?:\w+\s+){0,3}?(?:every|all|each)\s+"
                     r"(?:line|change|code|output)|\bhuman[- ]in[- ]the[- ]loop\b|\b(?:you are|you're|contributors?"
                     r" (?:is|are))\s+(?:fully\s+)?(?:responsible|accountable)\b",
                     "The person submitting must understand and stand behind every change."),
    "no-autonomous-agents": (r"(?i)\b(?:autonomous|unattended|fully[- ]automated)\s+(?:AI\s+)?(?:agents?|bots?|"
                             r"tools?|contributions?|pull requests?|PRs?)\b|\bagents?\s+(?:must|may|should|shall)\s+"
                             r"not\s+(?:open|submit|create|push|file)",
                             "No autonomous agents: a person drives the work and submits it."),
    "human-written-text": (r"(?i)\bin your own words\b|\bwritten by (?:a )?(?:human|person|you|yourself)\b|"
                           r"\bwrite\s+(?:\w+\s+){0,3}?yourself\b|\bnot\s+(?:be\s+)?(?:written|generated)\s+(?:by|with)"
                           r"\s+(?:an?\s+)?(?:AI|LLM)",
                           "Text (PR descriptions, issues, comments) must be written by the person: give them "
                           "notes, not finished prose."),
    "no-ai-coauthor": (r"(?i)co-?authored-?by",
                       "Mentions Co-authored-by: never list an AI tool as a co-author."),
    "first-timer-limits": (r"(?i)\b(?:one|1|two|2|three|3)\s+open\s+(?:pull requests?|PRs?|merge requests?)\b|\bvouch",
                           "Limits for new contributors (open-PR limits or vouching): check them before opening "
                           "anything."),
    "good-first-issues": (r"(?i)good[- ]first[- ]issues?",
                          "Mentions good first issues: these are often kept for people learning the project."),
}
FLAGS = {k: (re.compile(p), m) for k, (p, m) in FLAGS.items()}
DCO = re.compile(r"(?i)\bsigned-off-by\b|\bDCO\b|developer certificate of origin")
CLA = re.compile(r"(?i)contributor licen[cs]e agreement|\bI?CLAs?\b|cla[- ]assistant|cla\.developers\.google\.com|"
                 r"\beasycla\b|opensource\.microsoft\.com/cla|\bcla[- ]?bot\b")
CLA_NAME = r"(?:I?CLAs?|contributor licen[cs]e agreements?)\b"
NO_CLA = re.compile(r"(?i)\bno\s+(?:\w+\s+){0,2}" + CLA_NAME +
                    r"|\bno\s+need\b[^.\n]{0,30}?\b" + CLA_NAME +
                    r"|(?:\bnot|n't)\s+(?:\w+\s+){0,2}(?:require|need|ask|have|use)\w*\s+(?:\w+\s+){0,3}?" + CLA_NAME +
                    r"|\b" + CLA_NAME + r"\s+(?:is|are)\s+not\s+(?:required|needed|necessary)" +
                    r"|\bwithout\s+(?:signing\s+)?(?:an?\s+)?" + CLA_NAME)
CLA_STRONG = re.compile(r"(?i)cla[- ]assistant|cla\.developers\.google\.com|\beasycla\b|opensource\.microsoft\.com/cla|"
                        r"\bcla[- ]?bot\b")
README_CLA_HEADING = re.compile(r"(?i)contribut|\bI?CLAs?\b|licen[cs]|legal|pull request")
CLA_FILES = ("CLA.md", "cla.md", "CLA.txt", "CLA", ".github/CLA.md", ".clabot", ".github/cla.yml")
CLA_WORKFLOW = re.compile(r"(?i)contributor-assistant/github-action|cla-assistant|"
                          r"\bcla[- ]?(?:bot|check|signatures?)\b|\beasycla\b|^\s*name:\s*[\"']?CLA\b", re.M)
URL = re.compile(r"https?://[^\s)>\]\"'`]+")
POLICY_LINK = re.compile(r"(?i)polic|contribut|guideline|\bai\b|[/_-]ai[/_.#-]|llm|generative|slop|agent|disclos")
NOT_POLICY_LINK = re.compile(r"(?i)wikipedia\.org|shields\.io|badge|\.(?:svg|png|jpe?g|gif)(?:$|\?)|/press-release/|"
                             r"arxiv\.org")

BLOCK = re.compile(r"^[ \t]*(```|~~~)[ \t]*ai-contribution-policy[ \t]*\n(.*?)^[ \t]*\1[ \t]*$", re.M | re.S)
SPEC = {
    "version": None,
    "ai-assistance": {"allowed", "ask-first", "not-accepted"},
    "disclosure": {"assisted-by", "pr-description", "both", "not-needed"},
    "issue-first": {"yes", "no"},
    "agent-opened-prs": {"yes", "no"},
    "human-written-text": {"yes", "no"},
    "details": None,
}


def parse_block(text):
    """Parse an ```ai-contribution-policy block. Returns (values, problems) or None."""
    m = BLOCK.search(text)
    if not m:
        return None
    values, problems = {}, []
    for raw in m.group(2).splitlines():
        line = re.split(r"\s#", raw, maxsplit=1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            problems.append(f"not a key: value line: {line}")
            continue
        key, value = (s.strip() for s in line.split(":", 1))
        key, value_l = key.lower(), value.lower()
        if key not in SPEC:
            problems.append(f"unknown key: {key}")
            continue
        allowed = SPEC[key]
        if allowed is not None and value_l not in allowed:
            problems.append(f"{key}: '{value}' is not one of {', '.join(sorted(allowed))}")
            continue
        values[key] = value if allowed is None else value_l
    return values, problems


def paragraphs(text):
    """Yield (heading, first_line_number, [lines]) for each blank-line separated paragraph. Code blocks are skipped."""
    heading, buf, start, fence = "", [], 0, None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        f = re.match(r"^\s*(```|~~~)", line)
        if fence or f:
            if buf:
                yield heading, start, buf
                buf = []
            if f and fence is None:
                fence = f.group(1)
            elif f and f.group(1) == fence:
                fence = None
            continue
        md = re.match(r"^\s{0,3}#{1,6}\s+(.*)", line)
        rst = i + 1 < len(lines) and line.strip() and re.match(r"^([=\-~^\"'`#*+])\1{2,}\s*$", lines[i + 1]) \
            and len(lines[i + 1].strip()) >= len(line.strip()) - 2
        if md or rst:
            if buf:
                yield heading, start, buf
                buf = []
            heading = (md.group(1) if md else line).strip()
            continue
        if not line.strip() or re.match(r"^([=\-~^\"'`#*+])\1{2,}\s*$", line):
            if buf:
                yield heading, start, buf
                buf = []
            continue
        if not buf:
            start = i + 1
        buf.append(line)
    if buf:
        yield heading, start, buf


def read_policy(repo):
    repo = Path(repo)
    files = candidate_files(repo)
    hits, block, block_where, block_problems, links, dco_where, agents_files, templates = [], None, "", [], [], "", [], []
    cla_where = ""

    for kind, rel in files:
        text = read_text(repo / rel)
        if not text:
            continue
        if kind != "agents" and not cla_where:
            n = cla_line(text, kind)
            cla_where = f"{rel.as_posix()}:{n}" if n else ""
        if kind == "agents":
            agents_files.append(str(rel))
        if kind == "template" and "pull_request" in str(rel).lower():
            templates.append(str(rel))
        if block is None:
            parsed = parse_block(text)
            if parsed:
                block, block_problems = parsed
                block_where = str(rel)
        if kind in ("contributing", "ai-policy") and not dco_where:
            for n, line in enumerate(text.splitlines(), 1):
                if DCO.search(line):
                    dco_where = f"{rel}:{n}"
                    break
        if kind == "agents":
            continue  # instructions for AI tools, not the contribution policy; reported separately
        for heading, start, lines in paragraphs(text):
            body = " ".join(l.strip() for l in lines)
            in_ai_heading = bool(AI_TERM.search(heading)) and bool(POLICY_HEADING.search(heading) or kind != "readme")
            mentions = bool(AI_TERM.search(body))
            if not (in_ai_heading or mentions):
                continue
            signals = set()
            prose = []
            for line in lines:
                if CHECKBOX.match(line) and AI_TERM.search(line):
                    # "[ ] No LLMs were used" means AI is not accepted. "[ ] I used AI and say how", or a choice
                    # like "I read the AI guidelines, or I am not using AI", means it is accepted with disclosure.
                    pure_no = NEGATION.search(line) and not re.search(
                        r"(?i)\bor\s+(?:I|you|we)\b|guideline|responsib|understand|disclos|describ|explain|review", line)
                    in_line = scan_signals(CHECKBOX.sub("", line))
                    signals.add("ban-core" if pure_no or "ban-core" in in_line else "disclose")
                else:
                    prose.append(line.strip())
            signals |= scan_signals(" ".join(prose))
            if kind in ("readme", "template") or (kind == "contributing" and not in_ai_heading):
                # Elsewhere an AI mention only counts when it reads like a rule.
                if not signals and not (mentions and POLICY_WORD.search(body) and kind != "readme"):
                    continue
            flags = set() if kind == "readme" else {name for name, (pat, _) in FLAGS.items() if pat.search(body)}
            if "good-first-issues" in flags and not signals:
                flags.discard("good-first-issues")
            hits.append({"file": str(rel), "line": start, "heading": heading, "text": body,
                         "signals": signals, "flags": flags, "kind": kind})
            if kind in ("ai-policy", "contributing"):
                links += [u.rstrip(".,;") for u in URL.findall(body)
                          if POLICY_LINK.search(u) and not NOT_POLICY_LINK.search(u)]

    signals = set().union(*[h["signals"] for h in hits]) if hits else set()
    prose_stance = decide_stance(signals, bool(hits))
    if block and block.get("ai-assistance"):
        a, d = block["ai-assistance"], block.get("disclosure", "")
        stance = {"not-accepted": "not-accepted", "ask-first": "ask-first"}.get(a) or \
            ("allowed" if d == "not-needed" else "disclose" if d else "allowed")
    else:
        stance = decide_stance(signals, bool(hits))

    all_text = " ".join(h["text"] for h in hits)
    if block and block.get("disclosure"):
        disclosure = block["disclosure"]
    elif re.search(r"\bAssisted-by\b", all_text):
        disclosure = "assisted-by"
    elif re.search(r"\[\s?[xX ]?\s?\]", all_text):
        disclosure = "checkbox"
    elif "disclose" in signals:
        disclosure = "pr-description"
    else:
        disclosure = ""

    flags = {}
    for h in hits:
        for f in h["flags"]:
            flags.setdefault(f, f"{h['file']}:{h['line']}")
    if block:
        if block.get("issue-first") == "yes":
            flags.setdefault("issue-first", block_where)
        if block.get("agent-opened-prs") == "no":
            flags.setdefault("no-autonomous-agents", block_where)
        if block.get("human-written-text") == "yes":
            flags.setdefault("human-written-text", block_where)

    return {
        "stance": stance, "prose_stance": prose_stance, "disclosure": disclosure, "flags": flags, "hits": hits,
        "block": block, "block_where": block_where, "block_problems": block_problems,
        "links": list(dict.fromkeys(links))[:5], "dco": dco_where, "cla": cla_where or cla_config(repo),
        "agents_files": agents_files, "templates": templates,
        "files_read": [str(rel) for _, rel in files],
    }


def cla_line(text, kind):
    """The line number where the text asks for a signed CLA, or 0. A README counts only in a contributing or legal
    section or with a CLA bot link, so a README that merely talks about CLAs is not a requirement."""
    heading = ""
    for n, line in enumerate(text.splitlines(), 1):
        h = re.match(r"^\s{0,3}#{1,6}\s+(.*)", line)
        if h:
            heading = h.group(1)
        if not CLA.search(line) or NO_CLA.search(re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)):
            continue
        if kind == "readme" and not (CLA_STRONG.search(line) or README_CLA_HEADING.search(heading)):
            continue
        return n
    return 0


def cla_config(repo):
    """Where a CLA document, bot or check is set up in the repository, or ''."""
    repo = Path(repo)
    for name in CLA_FILES:
        if (repo / name).is_file():
            return name
    wf = repo / ".github" / "workflows"
    if wf.is_dir():
        for path in sorted(wf.glob("*.y*ml"))[:30]:
            text = read_text(path)
            m = CLA_WORKFLOW.search(text)
            if m:
                line = text.count("\n", 0, m.start()) + 1
                return f"{path.relative_to(repo).as_posix()}:{line}"
    return ""


# --------------------------------------------------------------------------
# Policy: the shared list of known project policies
# --------------------------------------------------------------------------


def remote_keys(repo):
    out = git(repo, "remote", "-v") or ""
    keys = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        m = re.match(r"^(?:[\w.+-]+@)?([\w.-]+):(?!//)(.+)$", url) or \
            re.match(r"^\w+://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", url)
        if not m:
            continue
        host, path = m.group(1).lower(), m.group(2).strip("/")
        path = path[:-4] if path.endswith(".git") else path
        key = f"{host}/{path}".lower()
        entry = (0 if name == "upstream" else 1, name, key)
        if entry not in keys:
            keys.append(entry)
    return [(name, key) for _, name, key in sorted(keys)]


def known_policy(repo):
    try:
        data = json.loads(KNOWN_POLICIES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, []
    remotes = remote_keys(repo)
    exact, wildcard = {}, {}
    for e in data.get("entries", []):
        for k in e.get("repos", []):
            (wildcard if k.endswith("/*") else exact)[k[:-2] if k.endswith("/*") else k] = e
    for name, key in remotes:
        if key in exact:
            return dict(exact[key], snapshot=data.get("snapshot", ""), matched=key, remote=name), remotes
    for name, key in remotes:
        owner = "/".join(key.split("/")[:2])
        if owner in wildcard:
            return dict(wildcard[owner], snapshot=data.get("snapshot", ""), matched=owner + "/*", remote=name), remotes
    return None, remotes


# --------------------------------------------------------------------------
# Policy: project checks (what the project itself runs)
# --------------------------------------------------------------------------


CI_CHECK = re.compile(r"(?i)\btest|lint|check|\bfmt\b|format|\btox\b|pytest|ruff|mypy|clippy|\bvet\b|eslint|"
                      r"prettier|black|flake8|\bmake\b|\bbuild\b|\bnox\b|typecheck|\btsc\b|\bctest\b|meson")
CI_SKIP = re.compile(r"(?i)release|deploy|publish|upload|docker push|\bgh\s|git push|secret|token|\$\{\{|"
                     r"apt-get|brew install|pip install|npm ci\b|npm install|choco ")


def project_commands(repo):
    repo, cmds = Path(repo), []
    pkg = repo / "package.json"
    if pkg.exists():
        try:
            scripts = json.loads(read_text(pkg)).get("scripts", {}) or {}
        except ValueError:
            scripts = {}
        runner = "pnpm" if (repo / "pnpm-lock.yaml").exists() else "yarn" if (repo / "yarn.lock").exists() \
            else "bun" if (repo / "bun.lockb").exists() or (repo / "bun.lock").exists() else "npm"
        for s in ("test", "lint", "typecheck", "check", "format:check", "build"):
            if s in scripts:
                cmds.append(f"{runner} run {s}" if not (s == "test" and runner == "npm") else "npm test")
    mk = read_text(repo / "Makefile")
    for target in ("test", "check", "lint", "fmt", "format"):
        if re.search(rf"(?m)^{target}\s*:", mk):
            cmds.append(f"make {target}")
    if (repo / "tox.ini").exists():
        cmds.append("tox")
    if (repo / "noxfile.py").exists():
        cmds.append("nox")
    if (repo / "Cargo.toml").exists():
        cmds += ["cargo test", "cargo clippy", "cargo fmt --check"]
    if (repo / "go.mod").exists():
        cmds += ["go test ./...", "go vet ./..."]
    ci = []
    wf = repo / ".github" / "workflows"
    if wf.is_dir():
        for path in sorted(wf.glob("*.y*ml"))[:12]:
            for m in re.finditer(r"(?m)^[ \t]*-?[ \t]*run:[ \t]+(?![|>])([^\n]+)$", read_text(path)):
                c = m.group(1).strip().strip("'\"")
                if c and len(c) <= 100 and CI_CHECK.search(c) and not CI_SKIP.search(c) and c not in ci:
                    ci.append(c)
    return list(dict.fromkeys(cmds)), ci[:10]


# --------------------------------------------------------------------------
# Policy: findings
# --------------------------------------------------------------------------

STANCE_TEXT = {
    "not-accepted": "This project does not accept AI-assisted contributions. Stop and tell the person, quoting the "
                    "rule. Do not reword the change to hide AI use.",
    "restricted": "AI help is accepted here only under conditions (some uses are not accepted). Read the lines "
                  "below with the person and follow every condition.",
    "ask-first": "The project asks you to check with maintainers before using AI help. Ask before writing code.",
    "disclose": "AI help is accepted with disclosure.",
    "allowed": "AI help is accepted here.",
    "unclear": "The project mentions AI, but the rule is unclear. Show the person these lines and ask before going on.",
    "silent": "No AI contribution policy found in the repository. It may be on the project's website: check the "
              "README and contributing links. When in doubt, disclose.",
}
STANCE_LEVEL = {"not-accepted": "stop", "restricted": "check", "ask-first": "fix", "unclear": "fix",
                "disclose": "check", "allowed": "check", "silent": "check"}
DISCLOSURE_TEXT = {
    "assisted-by": "Disclose with an `Assisted-by:` trailer in the commit message, in the exact format the project "
                   "gives.",
    "both": "Disclose in the PR description and with an `Assisted-by:` trailer.",
    "pr-description": "Disclose in the pull request description.",
    "checkbox": "The templates have an AI checkbox: fill it in honestly.",
    "not-needed": "The project says disclosure is not needed. A short note is still welcome.",
}


def policy_findings(repo):
    p = read_policy(repo)
    known, remotes = known_policy(repo)
    out = []
    best = {}
    groups = {"ban": ("ban-core", "ban-partial"), "disclose": ("disclose",), "allow": ("allow-strong", "allow-minor")}
    for group, names in groups.items():
        for name in names:  # strongest kind first, then the earliest line
            h = next((h for h in p["hits"] if name in h["signals"]), None)
            if h:
                best[group] = h
                break
    first = best.get("ban") or best.get("disclose") or best.get("allow") or (p["hits"][0] if p["hits"] else None)

    if p["block"] is not None:
        where = p["block_where"]
        out.append(Finding("info", "policy-block", "The project publishes an ai-contribution-policy block: it is "
                           "the authoritative answer.", where, ", ".join(f"{k}: {v}" for k, v in p["block"].items())))
        for prob in p["block_problems"]:
            out.append(Finding("check", "policy-block-problem", f"Policy block problem: {prob}", where))
        accepts = {"allowed", "disclose"}
        if (p["stance"] in accepts and p["prose_stance"] == "not-accepted") or \
                (p["stance"] == "not-accepted" and p["prose_stance"] in accepts):
            out.append(Finding("check", "policy-mismatch", f"The written policy reads as '{p['prose_stance']}' but the "
                               f"policy block says '{p['stance']}'. Follow the stricter one and tell the person "
                               "(maintainers: make them agree).", where))

    stance = p["stance"]
    msg = STANCE_TEXT[stance]
    if stance in ("disclose", "allowed", "restricted") and p["disclosure"]:
        msg += " " + DISCLOSURE_TEXT.get(p["disclosure"], "")
    elif stance == "allowed":
        msg += " No disclosure rule found; a short note in the PR is still the safe default."
    where = f"{first['file']}:{first['line']}" if first and not p["block"] else p["block_where"]
    quote = short(first["text"]) if first and not p["block"] else ""
    out.append(Finding(STANCE_LEVEL[stance], f"policy-{stance}", msg, where, quote))

    shown = {where}
    for s in ("ban", "disclose", "allow"):
        h = best.get(s)
        if h and f"{h['file']}:{h['line']}" not in shown and stance in ("restricted", "unclear"):
            shown.add(f"{h['file']}:{h['line']}")
            out.append(Finding("check", f"policy-line-{s}", "Also read this rule.", f"{h['file']}:{h['line']}",
                               short(h["text"])))

    for name, where in p["flags"].items():
        if name == "good-first-issues" and stance in ("allowed", "silent"):
            continue
        out.append(Finding("check", f"flag-{name}", FLAGS[name][1], where))
    if p["dco"]:
        out.append(Finding("check", "dco", "The project uses Signed-off-by (DCO). Only the person can add their own "
                           "sign-off; never add it for them.", p["dco"]))
    if p["cla"]:
        out.append(Finding("check", "cla", "The project asks contributors to sign a Contributor License Agreement "
                           "(CLA) before it can merge their work. Tell the person: only they can sign it, so never "
                           "sign it or answer the CLA bot for them.", p["cla"]))
    for url in p["links"]:
        out.append(Finding("check", "policy-link", f"The policy links to {url}. Open it and read it before going on."))

    if known:
        label = {"no": "does not accept AI-generated contributions", "yes": "accepts AI-assisted contributions",
                 "with-conditions": "accepts AI-assisted contributions only with conditions"}.get(
                     known["ai_allowed"], "has an AI policy")
        text = (f"A shared list of project AI policies (snapshot {known['snapshot']}) says {known['project']} "
                f"{label}. Read the policy: {known['policy_url']}")
        if known["ai_allowed"] == "no" and stance in ("silent", "unclear", "allowed"):
            out.append(Finding("stop", "known-not-accepted", text + " Stop and confirm with the person."))
        elif known["ai_allowed"] == "no" and stance != "not-accepted":
            out.append(Finding("fix", "known-not-accepted", text + " The repository says otherwise: read both."))
        else:
            out.append(Finding("check", "known-policy", text))
    elif remotes and not any(name == "upstream" for name, _ in remotes):
        out.append(Finding("info", "no-upstream", "If this is a fork, add the original project as the `upstream` "
                           "remote so its rules can be matched (git remote add upstream <url>)."))

    base_tree = None
    if git(repo, "rev-parse", "--git-dir") is not None:
        mb, _ = resolve_base(repo, None)
        if mb:
            base_tree = set((git(repo, "ls-tree", "-r", "--name-only", mb) or "").splitlines())
    for f in p["agents_files"]:
        if base_tree is not None and Path(f).as_posix() not in base_tree:
            continue  # added on this branch, so it is the contributor's file, not the project's
        out.append(Finding("check", "agents-file", f"The project has {f} with instructions for AI tools. Read it and "
                           "follow what applies to you."))
    for t in p["templates"][:2]:
        out.append(Finding("check", "pr-template", f"Use the project's pull request template: {t}"))
    cmds, ci = project_commands(repo)
    if cmds or ci:
        listed = "; ".join(cmds + [c for c in ci if c not in cmds][:6])
        out.append(Finding("info", "project-checks", f"What the project runs (config and CI): {listed}"))
    return out, p, known


# --------------------------------------------------------------------------
# Diff
# --------------------------------------------------------------------------

TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec|specs|testing)/|(^|/)test_[^/]+\.py$|_test\.(py|go|rb|exs?)$|"
                       r"\.(test|spec)\.[cm]?[jt]sx?$|Tests?\.(java|kt|cs|swift)$|_spec\.rb$|(^|/)conftest\.py$")
SKIP_MARK = re.compile(r"@pytest\.mark\.(skip|xfail)\b|\bpytest\.skip\(|@unittest\.skip|\bself\.skipTest\(|"
                       r"\b(?:it|test|describe|context)\.(?:skip|todo)\s*\(|\bx(?:it|describe|test)\s*\(|"
                       r"@Disabled\b|@Ignore\b|\bt\.Skip(?:f|Now)?\(|#\[ignore\]|\[Ignore\]|\bSkip\s*=\s*\"")
ASSERTION = re.compile(r"\bassert\w*\b|\bexpect\s*\(|\.should\b|\bt\.(?:Error|Fatal)\w*\(|\brequire\.\w+\(|"
                       r"\bassert_eq!|\bassert!|\bXCTAssert")
DEBUG = re.compile(r"\bdebugger;|\bconsole\.(?:log|debug)\(|\bbreakpoint\(\)|\bpdb\.set_trace\(|\bimport i?pdb\b|"
                   r"\bbinding\.pry\b|\bbyebug\b|\bdbg!\(|\bvar_dump\(|\bprint_r\(|"
                   r"\b(?:print|println!?|printf|puts|echo)\s*\(?\s*f?[\"'](?:DEBUG|debug|XXX|here\b)")
TODO = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
DOC_PATH = re.compile(r"(?i)\.(md|markdown|rst|txt|adoc|html?)$")
AGENT_PATH = re.compile(r"(^|/)(CLAUDE\.md|AGENTS\.md|GEMINI\.md|\.cursorrules|\.windsurfrules|\.clinerules|"
                        r"copilot-instructions\.md|\.aider[^/]*)$|(^|/)\.(cursor|claude|windsurf|codex|continue|roo|kiro|"
                        r"agents|gemini)/")
JUNK_PATH = re.compile(r"(^|/)(\.DS_Store|Thumbs\.db|desktop\.ini|npm-debug\.log[^/]*|yarn-error\.log)$|"
                       r"\.(log|swp|swo|orig|rej|bak|tmp)$|(^|/)\.(vscode|idea)/|\.(pem|p12|pfx)$|"
                       r"(^|/)id_(rsa|ed25519|ecdsa)$|(^|/)\.env(\.(?!example$|sample$|template$|dist$)[^/]*)?$")
NOTES_PATH = re.compile(r"(?i)(^|/)(notes?|todo|plan|planning|scratch|progress|summary|worklog|analysis|session|"
                        r"implementation[-_ ]?(plan|notes|summary))([-_.][\w-]*)?\.(md|txt)$")
LOCKS = {"package-lock.json": "package.json", "npm-shrinkwrap.json": "package.json", "yarn.lock": "package.json",
         "pnpm-lock.yaml": "package.json", "bun.lockb": "package.json", "bun.lock": "package.json",
         "poetry.lock": "pyproject.toml", "uv.lock": "pyproject.toml", "pdm.lock": "pyproject.toml",
         "Pipfile.lock": "Pipfile", "Cargo.lock": "Cargo.toml", "Gemfile.lock": "Gemfile", "go.sum": "go.mod",
         "composer.lock": "composer.json", "mix.lock": "mix.exs", "flake.lock": "flake.nix"}
AI_COAUTHOR = re.compile(r"(?im)^\s*co-authored-by:.*\b(claude|anthropic|copilot|chatgpt|openai|gpt|gemini|cursor|"
                         r"devin|codex|aider|windsurf|cline|codeium|tabnine|jules|\[bot\])")
AI_GENERATED = re.compile(r"(?im)\b(generated|created|made|written)\s+(with|by|using)\s+\[?(claude|copilot|chatgpt|"
                          r"cursor|codex|gemini|aider|windsurf|devin|ai)\b|🤖")
CHANGELOG_NAME = re.compile(r"\b(?:CHANGES|NEWS|HISTORY)(?:\.(?:md|rst|txt|adoc))?\b|(?i:\bchange ?log(?:\.(?:md|rst|"
                            r"txt|adoc))?\b|\b(?:changes|news|history)\.(?:md|rst|txt|adoc)\b)")
CHANGELOG_ASK = re.compile(r"(?i)\b(?:add|update|include|edit|writ|append|record|document)\w*\b|\bentry\b|\bentries\b")
CHANGELOG_NOT = re.compile(r"(?i)\bno need\b|\bdon'?t\b|\bdo not\b|\bnever\b|\bnot (?:necessary|required|needed)\b|"
                           r"\bmaintainers? (?:will |)(?:update|edit|write|handle|add)|\bautomatic\w*|\bgenerated\b")
CHANGELOG_CI = re.compile(r"(?i)towncrier\s+check|changeset\s+status|changeset-bot|reno\s+lint|news[- ]?fragments?|"
                          r"chronographer|changelog[-_ ]?(?:enforcer|check|checker|required|lint)|"
                          r"check[-_ ]?(?:changelog|news)|skip[- ](?:news|changelog)|no[- ]changelog")
FRAGMENT_SKIP = re.compile(r"(?i)(^|/)(\.gitignore|\.gitkeep|readme[^/]*|template[^/]*|config\.json)$")


def resolve_base(repo, base):
    candidates = [base] if base else ["upstream/HEAD", "upstream/main", "upstream/master", "origin/HEAD",
                                      "origin/main", "origin/master", "main", "master"]
    for ref in candidates:
        if git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}") is None:
            continue
        mb = (git(repo, "merge-base", ref, "HEAD") or "").strip()
        if mb:
            return mb, ref
    return None, None


def parse_patch(patch):
    """Return {path: {"added": [lines], "removed": [lines]}} from a -U0 patch."""
    files, cur = {}, None
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            cur = None
        elif line.startswith("+++ "):
            path = line[4:].strip()
            cur = None if path == "/dev/null" else files.setdefault(path[2:] if path.startswith("b/") else path,
                                                                      {"added": [], "removed": []})
        elif line.startswith("--- "):
            continue
        elif cur is not None and line.startswith("+"):
            cur["added"].append(line[1:])
        elif cur is not None and line.startswith("-"):
            cur["removed"].append(line[1:])
    return files


def toml_section(text, name):
    """The body of a [name] table in a TOML file, sub-tables included, or None."""
    m = re.search(rf"(?m)^\[{re.escape(name)}\]\s*$", text)
    if not m:
        return None
    rest = text[m.end():]
    end = re.search(rf"(?m)^\[(?!\[?{re.escape(name)}[.\]])", rest)
    return rest[: end.start()] if end else rest


def changelog_rule(repo, tree):
    """How the project wants changes recorded, from files it had before this change, or None.

    Returns {"kind": "fragments", "tool", "dir", "pattern"} for news-fragment tools (towncrier, changesets, reno,
    scriv, a changelog.d folder) or {"kind": "file", "file"} when the contributing guide or PR template asks for a
    CHANGELOG entry, plus "where" (the evidence) and "enforced" (a CI job checks it)."""
    repo = Path(repo)
    wf = repo / ".github" / "workflows"
    ci = " ".join(read_text(p) for p in sorted(wf.glob("*.y*ml"))[:30]) if wf.is_dir() else ""
    enforced = bool(CHANGELOG_CI.search(ci))

    def has_dir(d):
        return any(t.startswith(d + "/") for t in tree)

    def fragments(tool, d, where, pattern=None):
        d = d.strip().strip("/").removeprefix("./")
        return {"kind": "fragments", "tool": tool, "dir": d, "where": where, "enforced": enforced,
                "pattern": pattern or rf"^{re.escape(d)}/"}

    for cfg in ("towncrier.toml", ".towncrier.toml", "pyproject.toml"):
        section = toml_section(read_text(repo / cfg), "tool.towncrier") if cfg in tree else None
        if section is not None:
            main_table = re.split(r"(?m)^\s*\[", section, maxsplit=1)[0]  # [[tool.towncrier.type]] has its own
            m = re.search(r"(?m)^\s*directory\s*=\s*[\"']([^\"']+)[\"']", main_table)
            if m:
                return fragments("towncrier", m.group(1), cfg)
            return fragments("towncrier", "newsfragments", cfg, r"(^|/)newsfragments/")
    if ".changeset/config.json" in tree:
        return fragments("changesets", ".changeset", ".changeset/config.json", r"^\.changeset/[^/]+\.md$")
    if has_dir("releasenotes/notes"):
        return fragments("reno", "releasenotes/notes", "releasenotes/notes/", r"^releasenotes/notes/[^/]+\.ya?ml$")
    scriv, scriv_where = None, ""
    if "pyproject.toml" in tree:
        scriv, scriv_where = toml_section(read_text(repo / "pyproject.toml"), "tool.scriv"), "pyproject.toml"
    if scriv is None and "scriv.ini" in tree:
        scriv, scriv_where = read_text(repo / "scriv.ini"), "scriv.ini"
    if scriv is None and "setup.cfg" in tree:
        m = re.search(r"(?ms)^\[scriv\]\s*$(.*?)(?=^\[|\Z)", read_text(repo / "setup.cfg"))
        scriv, scriv_where = (m.group(1), "setup.cfg") if m else (None, "")
    if scriv is not None:
        m = re.search(r"(?m)^\s*fragment_directory\s*[=:]\s*[\"']?([^\"'\s]+)", scriv)
        return fragments("scriv", m.group(1) if m else "changelog.d", scriv_where)
    for d in ("changelog.d", "newsfragments"):
        if has_dir(d):
            return fragments(f"a {d} folder", d, f"{d}/")

    roots = sorted(t for t in tree if "/" not in t and re.match(r"(?i)(changelog|changes|news|history)\b", t))
    if not roots:
        return None
    for kind, rel in candidate_files(repo):
        if kind not in ("contributing", "template") or Path(rel).as_posix() not in tree:
            continue
        for n, line in enumerate(read_text(repo / rel).splitlines(), 1):
            m = CHANGELOG_NAME.search(line)
            if not m or not CHANGELOG_ASK.search(line) or CHANGELOG_NOT.search(line):
                continue
            named = m.group(0).lower().replace(" ", "")
            target = next((t for t in roots if t.lower() == named), None) or \
                next((t for t in roots if t.lower().startswith(named.split(".")[0])), None) or roots[0]
            return {"kind": "file", "file": target, "where": f"{Path(rel).as_posix()}:{n}", "enforced": enforced}
    return None


def is_source_change(path):
    """True for changes that usually need a changelog entry: not docs, tests, CI, lockfiles or dotfiles."""
    p = path.replace("\\", "/")
    if DOC_PATH.search(p) or TEST_PATH.search(p) or Path(p).name in LOCKS:
        return False
    return not (p.startswith((".github/", "docs/", "doc/", ".changeset/")) or ("/" not in p and p.startswith(".")))


def diff_findings(repo, base=None):
    out = []
    if git(repo, "rev-parse", "--git-dir") is None:
        return [Finding("info", "not-git", "Not a git repository: skipped the diff checks.")], {}
    mb, ref = resolve_base(repo, base)
    if not mb:
        return [Finding("fix", "no-base", "Could not find the branch to compare against. Pass --base, for example "
                        "--base upstream/main.")], {}
    status = git(repo, "diff", "--name-status", "-M", mb) or ""
    changes = []
    for line in status.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changes.append((parts[0][0], parts[-1], parts[1] if parts[0][0] == "R" else None))
    untracked = [p for p in (git(repo, "ls-files", "--others", "--exclude-standard") or "").splitlines() if p]
    numstat = git(repo, "diff", "--numstat", "-M", mb) or ""
    added_lines = removed_lines = 0
    per_file = {}
    for line in numstat.splitlines():
        a, d, path = (line.split("\t") + ["", ""])[:3]
        path = path.split(" => ")[-1].replace("}", "").replace("{", "") if " => " in path else path
        if a.isdigit() and d.isdigit():
            added_lines += int(a)
            removed_lines += int(d)
            per_file[path] = (int(a), int(d))
    ws_numstat = git(repo, "diff", "--numstat", "-w", "--ignore-blank-lines", "-M", mb) or ""
    ws_changed = {}
    for line in ws_numstat.splitlines():
        a, d, path = (line.split("\t") + ["", ""])[:3]
        if a.isdigit() and d.isdigit():
            ws_changed[path] = int(a) + int(d)
    patch = parse_patch(git(repo, "diff", "-U0", "-M", "--no-color", mb) or "")
    summary = {"base": ref, "merge_base": mb[:12], "files": len(changes) + len(untracked),
               "added": added_lines, "removed": removed_lines, "untracked": untracked}

    if not changes and not untracked:
        out.append(Finding("info", "empty", f"No changes compared with {ref}."))
    paths = {p for _, p, _ in changes}
    tree = set((git(repo, "ls-tree", "-r", "--name-only", mb) or "").splitlines())

    for kind, path, old in changes + [("?", p, None) for p in untracked]:
        new_file = kind in ("A", "?")
        state = "untracked" if kind == "?" else {"A": "added", "M": "changed", "D": "deleted", "R": "renamed"}.get(
            kind, "changed")
        if AGENT_PATH.search(path) and kind != "D":
            if new_file:
                out.append(Finding("fix", "agent-file", f"{path} ({state}) is a file for your own AI tooling. It does "
                                   "not belong in their repository: leave it out of the change.", path))
            else:
                out.append(Finding("check", "agent-file-edit", f"You changed the project's {path}. Only do that if the "
                                   "issue asks for it.", path))
        if JUNK_PATH.search(path) and kind != "D":
            out.append(Finding("fix", "junk-file", f"{path} ({state}) looks like a local, editor or secret file. "
                               "Remove it from the change.", path))
        if new_file and NOTES_PATH.search(path) and not path.lower().startswith(("docs/", "doc/")):
            out.append(Finding("fix", "notes-file", f"{path} ({state}) looks like working notes or a plan. Leave it "
                               "out unless the issue asked for it.", path))
        if kind == "D" and TEST_PATH.search(path):
            out.append(Finding("fix", "test-deleted", f"Deleted a test file: {path}. Only fine if the feature it "
                               "tested was removed on purpose. Say so in the PR, or restore it.", path))

    for path, (a, d) in per_file.items():
        if (a or d) and ws_changed.get(path, 0) == 0 and path in paths and not path.endswith((".md", ".rst", ".txt")):
            out.append(Finding("fix", "whitespace-only", f"Only whitespace or formatting changed in {path}. Revert "
                               "it unless the issue asks for reformatting.", path))

    for lock, manifest in LOCKS.items():
        for kind, path, _ in changes:
            if Path(path).name != lock or kind == "D":
                continue
            folder = str(Path(path).parent)
            man = manifest if folder == "." else f"{folder}/{manifest}"
            if kind == "A":
                others = [l for l, m in LOCKS.items() if m == manifest and l != lock and
                          (l if folder == "." else f"{folder}/{l}") in tree]
                if others:
                    out.append(Finding("fix", "wrong-lockfile", f"Added {path}, but the project uses {others[0]}. Use "
                                       "the project's package manager and drop the new lockfile.", path))
                    continue
            if man not in paths:
                out.append(Finding("check", "lockfile-churn", f"{path} changed but {man} did not. Lockfile churn often "
                                   "comes from a different tool version: revert it unless the change needs it.", path))

    for path, lines in patch.items():
        if DOC_PATH.search(path):
            continue  # examples in documentation are not code
        is_test = bool(TEST_PATH.search(path))
        skips = [l for l in lines["added"] if SKIP_MARK.search(l)]
        if skips:
            out.append(Finding("fix", "test-skipped", f"Added a skipped or disabled test in {path}. Never skip a test "
                               "to make it pass; if it is truly needed, explain why in the PR.", path, short(skips[0])))
        if is_test:
            gone = sum(1 for l in lines["removed"] if ASSERTION.search(l))
            new = sum(1 for l in lines["added"] if ASSERTION.search(l))
            if gone > new:
                out.append(Finding("check", "assertions-removed", f"{gone - new} more assertion line(s) removed than "
                                   f"added in {path}. Make sure no test was weakened to make it pass.", path))
        else:
            dbg = [l for l in lines["added"] if DEBUG.search(l)]
            if dbg:
                out.append(Finding("check", "debug-leftover", f"Debug code added in {path}. Remove leftovers before "
                                   "you share the change.", path, short(dbg[0])))
        todo = [l for l in lines["added"] if TODO.search(l)]
        if todo:
            out.append(Finding("check", "todo-added", f"New TODO/FIXME in {path}. Finish it or explain it in the PR.",
                               path, short(todo[0])))

    rule = changelog_rule(repo, tree)
    if rule:
        touched = [(k, p) for k, p, _ in changes if k != "D"] + [("?", p) for p in untracked]
        level = "fix" if rule["enforced"] else "check"
        if rule["kind"] == "fragments":
            frag = re.compile(rule["pattern"])
            added = [p for k, p in touched if k in ("A", "R", "?") and frag.search(p) and not FRAGMENT_SKIP.search(p)]
            source = [p for _, p in touched if is_source_change(p) and not frag.search(p)]
            if source and not added:
                out.append(Finding(level, "changelog-missing", f"The project records each change as a separate file "
                                   f"({rule['tool']}, in {rule['dir']}/), and this change adds none. Add one in the "
                                   "project's format, or ask the maintainers whether this change needs it.",
                                   rule["where"]))
        else:
            source = [p for _, p in touched if is_source_change(p) and p != rule["file"]]
            if source and rule["file"] not in {p for _, p in touched}:
                out.append(Finding(level, "changelog-missing", f"The project asks for an entry in {rule['file']} with "
                                   "each change, and this change doesn't touch it. Add one if the change is "
                                   "user-visible.", rule["where"]))

    nfiles = summary["files"]
    if nfiles > 15 or added_lines + removed_lines > 500:
        out.append(Finding("check", "large-change", f"Large change: {nfiles} files, +{added_lines}/-{removed_lines} "
                           "lines. Maintainers review small, focused PRs faster. Split it if you can, or say why it "
                           "must be big."))

    log = git(repo, "log", "--format=%h%x00%B%x1e", f"{mb}..HEAD") or ""
    for entry in log.split("\x1e"):
        if "\x00" not in entry:
            continue
        sha, body = entry.strip().split("\x00", 1)
        if AI_COAUTHOR.search(body):
            out.append(Finding("fix", "ai-coauthor", f"Commit {sha} lists an AI tool as Co-authored-by. Remove it and "
                               "disclose the way the project asks (often an `Assisted-by:` line or a PR note).", sha))
        elif AI_GENERATED.search(body):
            out.append(Finding("fix", "ai-generated-line", f"Commit {sha} has a 'Generated with' line. Replace it with "
                               "the disclosure format the project asks for.", sha))
    return out, summary


# --------------------------------------------------------------------------
# Pull request description
# --------------------------------------------------------------------------

FILLER = ["comprehensive", "robust", "seamless", "leverage", "delve", "in summary", "in conclusion",
          "i hope this helps", "let me know if", "as an ai", "certainly!", "great question", "cutting-edge",
          "game-changer", "game changer", "elevate", "streamline", "enhances the overall", "best practices",
          "rest assured", "it's worth noting", "it is worth noting", "plays a crucial role", "a testament to",
          "tapestry", "in today's"]
FILLER_RE = {w: re.compile(r"(?<!\w)" + re.escape(w[:-1] if w.endswith("e") and " " not in w else w).replace(
    r"\ ", r"\s+")) for w in FILLER}
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2705\u274C]")


def pr_findings(text, policy=None):
    out = []
    plain = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    words_n = len(re.findall(r"\b\w+\b", plain))
    if words_n > 350:
        out.append(Finding("check", "pr-long", f"{words_n} words. Maintainers skim: what changed, why (link the issue) "
                           "and how you tested usually fit in under 150."))
    emojis = EMOJI.findall(plain)
    if len(emojis) >= 3:
        out.append(Finding("fix", "pr-emoji", f"{len(emojis)} emoji. Drop them; they read as generated text."))
    low = plain.lower()
    found = [w for w, rx in FILLER_RE.items() if rx.search(low)]
    if found:
        out.append(Finding("fix", "pr-filler", "Generic filler words: " + ", ".join(found[:8]) + ". Say the specific "
                           "thing instead."))
    headings = len(re.findall(r"(?m)^\s{0,3}#{1,6}\s", plain))
    if headings > 5:
        out.append(Finding("check", "pr-headings", f"{headings} headings. Use the project's template, not a report."))
    bullets = len(re.findall(r"(?m)^\s*[-*+]\s", plain))
    if bullets > 15:
        out.append(Finding("check", "pr-bullets", f"{bullets} bullet points. Cut to what a reviewer needs."))
    if not re.search(r"(?i)#\d+|\b(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?|refs?|see)\b[^\n]{0,20}(?:#\d+|https?://)|"
                     r"https?://\S+/(?:issues|pull|merge_requests)/\d+", plain):
        out.append(Finding("check", "pr-no-issue", "No linked issue. Link the issue this solves (for example "
                           "'Fixes #123')."))
    if not re.search(r"(?i)\btest(?:s|ed|ing)?\b|\bverif\w*|\breproduc\w*|\bran\b|\bchecked\b|pytest|npm test|"
                     r"cargo test|go test|make check", plain):
        out.append(Finding("fix", "pr-no-testing", "Says nothing about testing. State exactly what you ran and what "
                           "you could not test."))
    if re.search(r"(?i)\ball tests pass(?:ed)?\b|\bfully tested\b|\bthoroughly tested\b", plain):
        out.append(Finding("check", "pr-test-claim", "Claims everything passes. Only keep that if you ran the full "
                           "suite in this session; otherwise say what you ran."))
    mentions_ai = re.search(r"(?i)\bAI\b|\bLLM|assisted|claude|copilot|chatgpt|codex|cursor|gemini|agent", plain)
    if policy and policy.get("stance") in ("disclose", "restricted") and not mentions_ai:
        out.append(Finding("fix", "pr-no-disclosure", "The project asks for AI disclosure and this description has "
                           "none. Add it in the project's format."))
    elif not mentions_ai:
        out.append(Finding("check", "pr-no-disclosure", "No AI disclosure. If AI helped, a short honest line is the "
                           "safe default (the person decides)."))
    return out


# --------------------------------------------------------------------------
# Fact check: files, lines and code names that a description or report mentions
# --------------------------------------------------------------------------

CODE_EXT = (r"py|pyi|pyx|c|h|cc|cpp|cxx|hpp|hh|hxx|rs|go|js|jsx|mjs|cjs|ts|tsx|mts|cts|java|kt|kts|rb|php|cs|swift|m|mm|"
            r"scala|sh|bash|zsh|fish|ps1|pl|pm|lua|r|jl|ex|exs|erl|hrl|hs|ml|mli|clj|cljs|dart|vue|svelte|html?|css|"
            r"scss|sass|less|json|jsonc|ya?ml|toml|ini|cfg|conf|xml|md|rst|txt|adoc|sql|proto|gradle|cmake|mk|in|lock|"
            r"tf|nix|zig|v|sv|vhdl?|s|asm|ipynb|cu|cuh|graphql|gql|csv|tex|el|vim|nim|cr|hcl|bzl|bazel|sol|f90|f")
FILE_NAME = r"[\w.+-]*\.(?:" + CODE_EXT + r")"
SEGMENTS = r"(?:\./)?[\w.+-]+(?:/[\w.+-]+)+"
LINE_SUFFIX = r"(?::(\d+)(?::\d+)?|#L(\d+)(?:-L?\d+)?|[\"']?,?\s+\(?(?:on\s+)?line\s+(\d+))?"
PATH_IN_TEXT = re.compile(r"(?<![\w.~/$@:%=+-])(" + SEGMENTS + r"\.(?:" + CODE_EXT + r"))(?![\w/])" + LINE_SUFFIX,
                          re.I)
SPAN_PATH = re.compile(r"^(" + SEGMENTS + r"/?)" + LINE_SUFFIX + r"$")
SPAN_FILE = re.compile(r"^(" + FILE_NAME + r")" + LINE_SUFFIX + r"$", re.I)
LINE_OF = re.compile(r"(?i)\bline\s+(\d+)\s+(?:of|in)\s+`?(" + SEGMENTS + r"\.\w+|" + FILE_NAME + r")`?")
INLINE_CODE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
FENCE = re.compile(r"^[ \t]*(```|~~~)[^\n]*\n(.*?)^[ \t]*\1[ \t]*$", re.M | re.S)
ANY_URL = re.compile(r"\b(?:https?|ftp|file)://\S+|\bwww\.\S+")
SYMBOL_SPAN = re.compile(r"^((?:[A-Za-z_$][\w$]*(?:::|\.|->|#))*([A-Za-z_$][\w$]*))(\(.*\))?;?$")
CALL = re.compile(r"(?<![\w.$>:#])((?:[A-Za-z_$][\w$]*(?:::|\.|->))*([A-Za-z_$][\w$]*))\(\)")
OUTSIDE_REPO = re.compile(r"^(?:node_modules|vendor|site-packages|\.?venv|env|dist|build|target|__pycache__|\.git|"
                          r"usr|lib/python\d|Library)/")
GENERIC_FILES = {"agents.md", "claude.md", "gemini.md", "ai_policy.md", "ai-policy.md", "security.md",
                 "code_of_conduct.md", "changelog.md", "readme.md", "contributing.md", "license", "license.md",
                 "package.json", "pyproject.toml", "cargo.toml", "go.mod", "pull_request_template.md"}
COMMON_NAMES = {"print", "len", "open", "main", "init", "new", "get", "set", "map", "filter", "str", "int", "float",
                "list", "dict", "range", "type", "super", "self", "this", "require", "import", "return", "exit",
                "assert", "format", "append", "join", "split", "strip", "replace", "sum", "min", "max", "sorted",
                "isinstance", "log", "error", "test", "run", "call", "read", "write", "close", "free", "malloc",
                "printf", "console", "describe", "expect", "push", "pop", "keys", "values", "items", "update"}


def mentions(text):
    """Files (with an optional line number) and code names that a piece of text refers to."""
    paths, names = {}, {}
    text = ANY_URL.sub(" ", re.sub(r"<!--.*?-->", "", text or "", flags=re.S))
    fences = [m.group(2) for m in FENCE.finditer(text)]
    prose = FENCE.sub(" ", text)
    spans = INLINE_CODE.findall(prose)
    plain = INLINE_CODE.sub(" ", prose)

    def add_path(token, *lines):
        token = token.rstrip("/")
        while token.startswith("./"):
            token = token[2:]
        first = token.split("/")[0]
        if not token or token.startswith(("../", "~", "path/to/")) or OUTSIDE_REPO.match(token) or \
                token.lower() in GENERIC_FILES:
            return
        if "/" in token and "." in first.strip(".") and not first.startswith("."):
            return  # a web address such as github.com/owner/repo
        line = next((int(n) for n in lines if n), None)
        if token not in paths or line:
            paths[token] = line or paths.get(token)

    def add_name(last, shown, strong):
        if len(last) < 3 or last.lower() in COMMON_NAMES or last.isdigit():
            return
        old = names.get(last)
        names[last] = (old[0] if old else shown, strong or bool(old and old[1]))

    for span in spans:
        span = span.strip()
        if " " in span.split("(")[0]:  # a command such as `pytest tests/test_x.py`
            for m in PATH_IN_TEXT.finditer(span):
                add_path(m.group(1), *m.groups()[1:])
            continue
        if not span or span.startswith(("-", "$", "/", "~", "<", "@")):
            continue
        m = SPAN_PATH.match(span) or SPAN_FILE.match(span)
        if m and not (SPAN_FILE.match(span) and span.endswith(")")):
            add_path(m.group(1), *m.groups()[1:])
            continue
        m = SYMBOL_SPAN.match(span)
        if not m:
            continue
        full, last, call = m.group(1), m.group(2), m.group(3)
        qualified = any(q in full for q in ("::", "->", "#"))
        if call or qualified or "_" in last.strip("_") or re.search(r"[a-z][A-Z]", last):
            add_name(last, full + ("()" if call else ""), bool(call))
    for chunk in [plain] + fences:
        for m in PATH_IN_TEXT.finditer(chunk):
            add_path(m.group(1), *m.groups()[1:])
    for m in LINE_OF.finditer(text):
        add_path(m.group(2), m.group(1))
    for m in CALL.finditer(plain):
        add_name(m.group(2), m.group(1) + "()", True)
    return paths, names


def repo_index(repo, base=None):
    """All files in the working tree and at the base commit, plus the lines the change removed."""
    if git(repo, "rev-parse", "--git-dir") is None:
        return {p.relative_to(repo).as_posix() for p in walk(repo, max_depth=12)}, None, ""
    files = set((git(repo, "ls-files", "--cached", "--others", "--exclude-standard") or "").splitlines())
    mb, _ = resolve_base(repo, base)
    removed = ""
    if mb:
        files |= set((git(repo, "ls-tree", "-r", "--name-only", mb) or "").splitlines())
        removed = "\n".join(line[1:] for line in (git(repo, "diff", "-U0", mb) or "").splitlines()
                            if line.startswith("-") and not line.startswith("---"))
    return {f for f in files if f}, mb, removed


def line_count(repo, path, mb):
    p = Path(repo) / path
    if p.is_file():
        return len(read_text(p, limit=20_000_000).splitlines())
    blob = git(repo, "show", f"{mb}:{path}") if mb else None
    return len(blob.splitlines()) if blob is not None else None


def name_in_repo(repo, name, removed, exclude=None):
    if removed and re.search(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])", removed):
        return True
    spec = ["--", ".", f":(exclude){exclude}"] if exclude else []
    try:
        r = subprocess.run(["git", "-C", str(repo), "grep", "-q", "-I", "-w", "-F", "--untracked", "-e", name, *spec],
                           capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return True  # can't tell: don't accuse
    return r.returncode != 1  # 0 found, 1 not found, anything else: can't tell


def reference_findings(repo, text, base=None, kind="text", source=None):
    """Flag files, line numbers and code names that the text mentions but the repository doesn't have.

    `source` is the file the text came from: if it sits inside the repository, it is left out of the search."""
    paths, names = mentions(text)
    if not paths and not names:
        return []
    files, mb, removed = repo_index(repo, base)
    exclude = None
    if source:
        try:
            exclude = Path(source).resolve().relative_to(Path(repo).resolve()).as_posix()
            files.discard(exclude)
        except ValueError:
            pass
    if not files:
        return []
    by_name, dirs = {}, set()
    for f in files:
        by_name.setdefault(f.rsplit("/", 1)[-1], []).append(f)
        parts = f.split("/")
        dirs.update("/".join(parts[:i]) for i in range(1, len(parts)))

    own_names = {Path(repo).resolve().name.lower()} | {k.rsplit("/", 1)[-1] for _, k in remote_keys(repo)}

    def resolve(p):
        first, _, rest = p.partition("/")
        if rest and first.lower() in own_names and resolve_plain(rest) is not None:
            return resolve_plain(rest)  # written from one folder up: "project/src/file.c"
        return resolve_plain(p)

    def resolve_plain(p):
        if p in files:
            return [p]
        if p in dirs:
            return []
        tail = "/" + p if "/" in p else None
        matches = [f for f in by_name.get(p.rsplit("/", 1)[-1], []) if tail is None or f.endswith(tail)]
        if matches or any(d.endswith("/" + p) for d in dirs):
            return matches
        return None

    when = " (before or after your change)" if mb and kind == "text" else ""
    out = []
    for p, line in paths.items():
        found = resolve(p)
        if found is None:
            if "/" in p:
                out.append(Finding("fix", "ref-missing-file", f"Mentions {p}, but there is no such file in this "
                                   f"repository{when}. Check the path; never cite a file you haven't opened."))
            else:
                out.append(Finding("check", "ref-unknown-file", f"Mentions {p}, but no file has that name in this "
                                   "repository. Make sure it is right."))
            continue
        counts = [c for c in (line_count(repo, f, mb) for f in found[:5]) if c is not None]
        if line and counts and line > max(counts):
            out.append(Finding("fix", "ref-bad-line", f"Points at line {line} of {p}, but the file has "
                               f"{max(counts)} lines. Check the line number.", p))
    if git(repo, "rev-parse", "--git-dir") is not None:
        ordered = sorted(names.items(), key=lambda kv: not kv[1][1])[:10]  # each miss is a full search
        for name, (shown, strong) in ordered:
            if name_in_repo(repo, name, removed, exclude):
                continue
            if strong:
                out.append(Finding("fix", "ref-missing-name", f"Mentions {shown}, but `{name}` appears nowhere in "
                                   f"this repository{when}. Check the name; if it is new or from another project, "
                                   "say so."))
            else:
                out.append(Finding("check", "ref-unknown-name", f"Mentions {shown}, which doesn't appear in this "
                                   "repository. Make sure the name is right."))
    return out[:12]


# --------------------------------------------------------------------------
# Bug and security reports
# --------------------------------------------------------------------------

REPORT_SCOPE = re.compile(r"(?i)\bissues?\b|bug reports?|security reports?|vulnerability reports?|\breports?\b")
REPRO = re.compile(r"(?im)steps to reproduce|to reproduce|reproduc|\brepro\b|proof of concept|\bPoC\b|minimal "
                   r"(?:example|script|case|program)|^\s*(?:\$|>>>|PS>|C:\\>)\s*\S")
VERSION = re.compile(r"(?i)\bv?\d+\.\d+(?:\.\d+)?\b|\bversion\b|\bcommit\b|\b[0-9a-f]{7,40}\b|\b(?:main|master|HEAD|"
                     r"trunk|nightly)\b")
EXPECTED = re.compile(r"(?i)\bexpect|\bactual|\binstead\b|\bshould\b|\bbut (?:it|got|gets|returns?|prints?|shows?)\b")
SPECULATIVE = re.compile(r"(?i)\b(?:could|may|might)\s+(?:potentially\s+|possibly\s+|theoretically\s+)?(?:allow|lead|"
                         r"result|enable|be (?:exploited|abused|used)|cause|expose|permit|introduce)|\bpotentially\b|"
                         r"\btheoretically\b|\bin theory\b")
SECURITY = re.compile(r"(?i)vulnerab|\bsecurity\b|\bexploit|\bCVE-\d|\bCVSS|attacker|buffer overflow|use[- ]after[- ]"
                      r"free|injection|\bRCE\b|denial of service|privilege escalation|\bXSS\b|\bSSRF\b")


def report_findings(repo, text, policy=None, source=None):
    """Checks for a bug or security report before it is filed."""
    repo = Path(repo)
    out = []
    plain = re.sub(r"<!--.*?-->", "", text or "", flags=re.S)
    if policy:
        ban = next((h for h in policy.get("hits", []) if "ban-partial" in h["signals"] and
                    REPORT_SCOPE.search(h["text"])), None)
        if ban:
            out.append(Finding("stop", "report-ai-not-accepted", "The project does not accept AI-written issues or "
                               "reports. Stop and tell the person.", f"{ban['file']}:{ban['line']}",
                               short(ban["text"])))
        if "human-written-text" in policy.get("flags", {}):
            out.append(Finding("fix", "report-human-written", "The project wants text written by people. Give the "
                               "person notes and let them write the report.", policy["flags"]["human-written-text"]))
    security = SECURITY.search(plain)
    has_fence = re.search(r"(?m)^[ \t]*(```|~~~)", plain)
    if not (REPRO.search(plain) or (has_fence and re.search(r"(?m)^\s*1[.)]\s", plain))):
        out.append(Finding("fix", "report-no-repro", "No way to reproduce it. Give exact steps or a minimal script, "
                           "and the output you got. Never send a report you have not reproduced."))
    if not VERSION.search(plain):
        out.append(Finding("check", "report-no-version", "Say which version or commit you tested."))
    if not EXPECTED.search(plain):
        out.append(Finding("check", "report-no-expected", "Say what you expected and what happened instead."))
    guesses = SPECULATIVE.findall(plain)
    if guesses and (security or len(guesses) >= 2):
        out.append(Finding("check", "report-speculative", "Speculative wording (\"could potentially…\"). Show it "
                           "happening; maintainers can't act on a maybe."))
    if security:
        sec = next((p for p in ("SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md", "SECURITY.rst",
                                "SECURITY.txt") if (repo / p).is_file()), None)
        out.append(Finding("check", "report-security", "This reads like a security report. Send it the private way "
                           "the project asks" + (f" ({sec})" if sec else " (look for a security policy or contact)") +
                           ", not as a public issue.", sec or ""))
    words_n = len(re.findall(r"\b\w+\b", plain))
    if words_n > 600:
        out.append(Finding("check", "report-long", f"{words_n} words. Lead with the steps to reproduce; cut the rest."))
    for f in pr_findings(plain, policy):
        if f.code in ("pr-emoji", "pr-filler", "pr-no-disclosure"):
            f.code = f.code.replace("pr-", "report-")
            out.append(f)
    return out + reference_findings(repo, plain, kind="report", source=source)


# --------------------------------------------------------------------------
# Online checks (opt-in): GitHub through the gh command line tool
# --------------------------------------------------------------------------

MAINTAINER = {"OWNER", "MEMBER", "COLLABORATOR"}
GOOD_LABEL = re.compile(r"(?i)accept|help[- ]wanted|good[- ]first|confirmed|approved|triaged|ready|contributions? welcome")
BAD_LABEL = re.compile(r"(?i)needs[- ]triage|needs[- ]discussion|question|wontfix|won't fix|duplicate|invalid|declined|"
                       r"not[- ]planned|blocked|on[- ]hold|stale")
CLAIM = re.compile(r"(?i)\b(?:i(?:'d| would)? like to (?:work|take)|i'?ll (?:work|take|fix)|i'?m working on|can i "
                   r"(?:work|take)|assign (?:it to )?me|working on (?:this|it))\b")
BEGINNER_LABEL = re.compile(r"(?i)good[- ]first|first[- ]timers?[- ]only|beginner")
TAKEN = {"issue-closed", "issue-assigned", "issue-not-ready", "issue-claimed", "duplicate-pr", "issue-reserved"}


class GhError(Exception):
    pass


def run_gh(args):
    """Run gh and parse its JSON output. Raises GhError with a readable message."""
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=60)
    except FileNotFoundError:
        raise GhError("the GitHub CLI (gh) is not installed") from None
    except subprocess.TimeoutExpired:
        raise GhError("gh took too long to answer") from None
    if r.returncode != 0:
        raise GhError(short(r.stderr or r.stdout or f"gh exited with {r.returncode}", 200))
    try:
        return json.loads(r.stdout or "null")
    except ValueError:
        raise GhError("gh returned something that is not JSON") from None


def github_slug(repo):
    for name, key in remote_keys(repo):
        parts = key.split("/")
        if parts[0] == "github.com" and len(parts) >= 3:
            return name, f"{parts[1]}/{parts[2]}"
    return None, None


def search_issues(query):
    data = run_gh(["api", "-X", "GET", "search/issues", "-f", f"q={query}", "-f", "per_page=30"])
    return (data or {}).get("items", [])


def issue_findings(repo, number, policy=None):
    """Is this issue open, unclaimed and wanted, and is someone already fixing it? Uses GitHub's REST API via gh.
    When it is not available, lists other open issues to offer instead. `policy` is what read_policy returned."""
    out = []
    _, slug = github_slug(repo)
    if not slug:
        return [Finding("fix", "no-github-remote", "Could not tell which GitHub project this is. Add the original "
                        "project as the `upstream` remote.")]
    try:
        issue = run_gh(["api", f"repos/{slug}/issues/{number}"])
    except GhError as e:
        return [Finding("fix", "issue-unavailable", f"Could not read issue #{number} in {slug}: {e}")]
    where = issue.get("html_url", f"{slug}#{number}")
    if "pull_request" in issue:
        return [Finding("fix", "issue-is-pr", f"#{number} in {slug} is a pull request, not an issue.", where)]
    out.append(Finding("info", "issue", f"#{number} in {slug}: {short(issue.get('title', ''), 100)}", where))
    if issue.get("state") != "open":
        out.append(Finding("fix", "issue-closed", f"Issue #{number} is {issue.get('state', 'closed')}. Pick an open "
                           "issue.", where))
    assignees = [a.get("login", "") for a in issue.get("assignees") or []]
    if assignees:
        out.append(Finding("fix", "issue-assigned", f"Issue #{number} is assigned to {', '.join(assignees)}. Pick "
                           "another one, or ask on the issue first.", where))
    labels = [l.get("name", "") for l in issue.get("labels") or []]
    bad = [l for l in labels if BAD_LABEL.search(l)]
    good = [l for l in labels if GOOD_LABEL.search(l)]
    if bad:
        out.append(Finding("fix", "issue-not-ready", f"Labels say it is not ready for a fix: {', '.join(bad)}.", where))
    reserved = bool(policy and "good-first-issues" in (policy.get("flags") or {}))
    beginner = [l for l in labels if BEGINNER_LABEL.search(l)]
    if reserved and beginner:
        out.append(Finding("check", "issue-reserved", f"Issue #{number} is labeled '{beginner[0]}', and the project's "
                           f"AI rules mention good first issues ({policy['flags']['good-first-issues']}). These are "
                           "often kept for people learning the project: read that rule, and if so, pick another issue.",
                           where))
    comments = []
    if issue.get("comments"):
        try:
            comments = run_gh(["api", f"repos/{slug}/issues/{number}/comments?per_page=100"]) or []
        except GhError:
            comments = []
    maintainer_said = any(c.get("author_association") in MAINTAINER for c in comments)
    if not good and not maintainer_said:
        out.append(Finding("check", "issue-not-accepted", "No maintainer has replied and no label says it is accepted. "
                           "Ask on the issue before writing code.", where))
    claims = [c for c in comments[-10:] if c.get("author_association") not in MAINTAINER and CLAIM.search(
        c.get("body") or "")]
    if claims:
        who = (claims[-1].get("user") or {}).get("login", "someone")
        out.append(Finding("check", "issue-claimed", f"{who} said they would work on it. Check with them first.",
                           where, short(claims[-1].get("body") or "", 120)))
    try:
        ref = re.compile(rf"#{number}\b|/issues/{number}\b")
        prs = search_issues(f"repo:{slug} is:pr is:open {number}")
        dupes = [p for p in prs if ref.search((p.get("title") or "") + " " + (p.get("body") or ""))]
        for p in dupes[:3]:
            out.append(Finding("fix", "duplicate-pr", f"Open pull request #{p['number']} already references this "
                               "issue. Review or test it instead of opening another.", p.get("html_url", "")))
    except GhError as e:
        out.append(Finding("check", "pr-search-failed", f"Could not search open pull requests: {e}"))
    try:
        mine = search_issues(f"repo:{slug} is:pr is:open author:@me")
        if mine:
            out.append(Finding("check", "open-prs", f"You already have {len(mine)} open pull request(s) in {slug}. "
                               "Some projects limit how many a newcomer may have open."))
    except GhError:
        pass
    if {f.code for f in out} & TAKEN and not (policy and policy.get("stance") == "not-accepted"):
        out.append(other_issues(slug, number, skip_beginner=reserved))
    return out


def other_issues(slug, number, skip_beginner=False, limit=5):
    """Open issues nobody is assigned to, to offer when the chosen one is taken. Accepted ones come first."""
    where = f"https://github.com/{slug}/issues"
    try:
        items = run_gh(["api", f"repos/{slug}/issues?state=open&sort=updated&per_page=50"]) or []
    except GhError as e:
        return Finding("check", "other-issues-unavailable", f"Could not list other open issues: {e}", where)
    picks = []
    for item in items:
        if "pull_request" in item or item.get("number") == number or item.get("assignees"):
            continue
        labels = [l.get("name", "") for l in item.get("labels") or []]
        if any(BAD_LABEL.search(l) for l in labels):
            continue
        if skip_beginner and any(BEGINNER_LABEL.search(l) for l in labels):
            continue
        picks.append((0 if any(GOOD_LABEL.search(l) for l in labels) else 1, item))
    picks = [item for _, item in sorted(picks, key=lambda p: p[0])][:limit]
    if not picks:
        return Finding("info", "other-issues", "No other open, unassigned issue looks ready. Suggest the person ask "
                       "the maintainers where help is wanted.", where)
    listed = "; ".join(f"#{item['number']} {short(item.get('title') or '', 60)}" for item in picks)
    return Finding("info", "other-issues", f"Other open issues nobody is assigned to, to offer the person instead: "
                   f"{listed}. Check one with `check.py issue <number>` before starting.", where)


def org_policy_findings(repo, local_stance):
    """Read an organisation-wide policy kept in OWNER/.github, as some projects do."""
    _, slug = github_slug(repo)
    if not slug:
        return []
    owner = slug.split("/")[0]
    try:
        listing = run_gh(["api", f"repos/{owner}/.github/contents"])
    except GhError:
        return []  # no organisation profile repository
    names = [f["path"] for f in listing or [] if f.get("type") == "file" and classify_file(Path(f["path"]))
             in ("ai-policy", "contributing")]
    if not names:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        for name in names[:5]:
            try:
                blob = run_gh(["api", f"repos/{owner}/.github/contents/{name}"])
                (Path(tmp) / name).write_bytes(base64.b64decode(blob.get("content", "")))
            except (GhError, ValueError):
                continue
        p = read_policy(tmp)
    if p["stance"] == "silent":
        return []
    first = next((h for h in p["hits"] if h["signals"]), p["hits"][0] if p["hits"] else None)
    where = f"{owner}/.github/{first['file']}" if first else f"{owner}/.github"
    level = STANCE_LEVEL[p["stance"]]
    if p["stance"] == "not-accepted" and local_stance not in ("silent", "unclear"):
        level = "fix"  # the repository's own rule may override the organisation's; read both
    return [Finding(level, f"org-policy-{p['stance']}", "Organisation-wide policy: " + STANCE_TEXT[p["stance"]], where,
                    short(first["text"]) if first else "")]


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------


def main(argv=None):
    ap = argparse.ArgumentParser(prog="check.py", description="sarwan_skill: no slop pull requests.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("policy", "diff", "pr", "all", "issue", "report"):
        sp = sub.add_parser(name)
        sp.add_argument("--repo", default=".", help="repository folder (default: current folder)")
        sp.add_argument("--json", action="store_true", help="print JSON")
        if name in ("diff", "all"):
            sp.add_argument("--base", help="branch or commit to compare with (default: upstream or origin main)")
        if name == "pr":
            sp.add_argument("file", help="file with the PR description, or - for stdin")
        if name == "report":
            sp.add_argument("file", help="file with the bug or security report, or - for stdin")
        if name == "all":
            sp.add_argument("--pr", help="file with the PR description draft")
            sp.add_argument("--issue", type=int, help="issue number this work is for (needs --online)")
        if name == "issue":
            sp.add_argument("number", type=int, help="issue number in the upstream project")
        if name in ("policy", "all"):
            sp.add_argument("--online", action="store_true",
                            help="also ask GitHub through gh (organisation-wide policy, issue status, duplicate PRs)")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"not a folder: {repo}", file=sys.stderr)
        return 2

    sections, extra = [], {}
    policy = None
    if args.cmd in ("policy", "all", "pr", "report"):
        findings, policy, known = policy_findings(repo)
        if getattr(args, "online", False):
            findings += org_policy_findings(repo, policy["stance"])
        if args.cmd != "pr":
            sections.append(("Project rules", findings))
    if args.cmd == "issue" or (args.cmd == "all" and args.online and args.issue):
        number = args.number if args.cmd == "issue" else args.issue
        sections.append((f"Issue #{number}", issue_findings(repo, number, policy or read_policy(repo))))
    if args.cmd in ("policy", "all", "pr", "report"):
        extra["policy"] = {"stance": policy["stance"], "disclosure": policy["disclosure"],
                           "flags": sorted(policy["flags"]), "block": policy["block"],
                           "known_list_match": known and {k: known[k] for k in ("project", "ai_allowed", "policy_url",
                                                                              "matched")},
                           "files_read": policy["files_read"][:30]}
    if args.cmd in ("diff", "all"):
        findings, summary = diff_findings(repo, args.base)
        sections.append(("Your change", findings))
        extra["diff"] = summary
    text_file = getattr(args, "file", None) or getattr(args, "pr", None)
    if text_file:
        text = sys.stdin.read() if text_file == "-" else Path(text_file).read_text(encoding="utf-8", errors="replace")
        source = None if text_file == "-" else text_file
        if args.cmd == "report":
            sections.append(("Report", report_findings(repo, text, policy, source)))
        else:
            sections.append(("Pull request text", pr_findings(text, policy) +
                             reference_findings(repo, text, getattr(args, "base", None), source=source)))

    everything = [f for _, fs in sections for f in fs]
    level = worst(everything) if everything else "info"
    if args.json:
        print(json.dumps({"result": level, "sections": {t: [f.as_dict() for f in fs] for t, fs in sections},
                          **extra}, indent=2, ensure_ascii=False))
    else:
        print("sarwan_skill check" + (f" ({repo.name})" if repo.name else ""))
        if "diff" in extra and extra["diff"].get("base"):
            d = extra["diff"]
            print(f"compared with {d['base']} ({d['merge_base']}): {d['files']} files, +{d['added']}/-{d['removed']}")
        for title, fs in sections:
            print_section(title, fs)
        verdict = {"stop": "STOP. Tell the person before doing anything else.",
                   "fix": "Fix the items marked FIX, then run this again.",
                   "check": "Nothing blocking. Read the CHECK items.",
                   "info": "Nothing to fix."}[level]
        print(f"\nResult: {verdict}")
    return {"stop": 2, "fix": 1}.get(level, 0)


if __name__ == "__main__":
    sys.exit(main())
