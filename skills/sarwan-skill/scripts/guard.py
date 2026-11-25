#!/usr/bin/env python3
"""sarwan_skill guard: run the checks automatically before a contribution leaves the machine.

  python3 guard.py claude-code               Claude Code PreToolUse hook (reads the hook JSON on stdin)
  python3 guard.py pre-push NAME URL         git pre-push hook (git passes the remote name and URL)
  python3 guard.py sendemail-validate FILE   git send-email hook (git passes each patch email)
  python3 guard.py install [--repo DIR]      add both git hooks to a repository (works with any agent)

It acts only when work is headed to a project the person does not own: `git push` to
a remote owned by someone else, a pull request (`gh pr create`, `glab mr create`), a
patch sent by email (`git send-email`, `b4 send`) or a new issue (`gh issue create`,
`glab issue create`). Pushing to your own fork is not blocked.

  - The project does not accept AI-assisted contributions -> blocked.
  - Something to fix (agent files, skipped tests, AI co-author lines...) -> the person is asked.
  - Otherwise -> allowed, silently.

The person can turn it off for one command with SARWAN_SKILL_GUARD=off. An agent must never do that itself.
If anything goes wrong inside the guard, it lets the command through and says why on stderr.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402

ACTIONS = re.compile(r"(?:^|[;&|(]\s*|\s)(git(?:\s+-C\s+\S+)?\s+(?:push|send-email)\b|b4\s+send\b|"
                     r"gh\s+(?:pr|issue)\s+create\b|glab\s+(?:mr|issue)\s+create\b|hub\s+pull-request\b)")
NOT_SENT = {"git": {"--dry-run"}, "b4": {"--dry-run", "-d", "--reflect", "--output-dir", "-o"}}  # nothing goes out
MARK = "# sarwan_skill"
HOOKS = {"pre-push": ('pre-push "$1" "$2"', "before git push", "git push --no-verify"),
         "sendemail-validate": ('sendemail-validate "$1"', "before git send-email", "git send-email --no-validate")}


# --------------------------------------------------------------------------
# Who owns what
# --------------------------------------------------------------------------


def github_login():
    """The person's GitHub login, from local config only (no network)."""
    if os.environ.get("SARWAN_SKILL_GITHUB_USER"):
        return os.environ["SARWAN_SKILL_GITHUB_USER"].lower()
    config_dir = os.environ.get("GH_CONFIG_DIR") or (
        Path(os.environ.get("APPDATA", "")) / "GitHub CLI" if os.name == "nt" else
        Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "gh")
    hosts = Path(config_dir) / "hosts.yml"
    try:
        text = hosts.read_text(encoding="utf-8")
        m = re.search(r"(?ms)^github\.com:\s*\n(?:\s+.*\n)*?\s+user:\s*(\S+)", text)
        if m:
            return m.group(1).strip("'\"").lower()
    except OSError:
        pass
    login = (check.git(Path.cwd(), "config", "--get", "github.user") or "").strip()
    return login.lower() or None


def owner_of(key):
    """'github.com/owner/repo' -> 'owner'."""
    parts = key.split("/")
    return parts[1].lower() if len(parts) >= 3 else None


def key_from_url(url):
    m = re.match(r"^(?:[\w.+-]+@)?([\w.-]+):(?!//)(.+)$", url) or \
        re.match(r"^\w+://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", url)
    if not m:
        return None
    path = m.group(2).strip("/")
    path = path[:-4] if path.endswith(".git") else path
    return f"{m.group(1).lower()}/{path}".lower()


def split_words(command):
    try:
        return shlex.split(command or "", posix=True)
    except ValueError:  # unbalanced quotes, heredocs and the like
        return (command or "").split()


def flag_value(words, *flags):
    for flag in flags:
        if flag in words and words.index(flag) + 1 < len(words):
            return words[words.index(flag) + 1]
    return None


def target_of(repo, command):
    """Which repository the command sends work to: (key or None, action or None)."""
    words = split_words(command)
    remotes = dict(check.remote_keys(repo))
    home = remotes.get("upstream") or remotes.get("origin")
    if "send-email" in words or ("b4" in words and "send" in words):
        if NOT_SENT["git" if "send-email" in words else "b4"] & set(words):
            return None, None
        return home, "patch email"
    opens_pr = ("pr" in words or "mr" in words) and "create" in words or "pull-request" in words
    opens_issue = "issue" in words and "create" in words and ("gh" in words or "glab" in words)
    if opens_pr or opens_issue:
        action = "pull request" if opens_pr else "issue"
        value = flag_value(words, "--repo", "-R")
        if value:
            value = value.lower()
            return (value if value.count("/") >= 2 else f"github.com/{value}"), action
        return home, action
    if "push" in words:
        after = words[words.index("push") + 1:]
        names = [w for w in after if not w.startswith("-")]
        remote = names[0] if names else "origin"
        return remotes.get(remote) or key_from_url(remote), "push"
    return None, None


def is_someone_elses(key, login):
    owner = owner_of(key or "")
    if not owner:
        return None  # unknown
    if login is None:
        return None
    return owner != login


# --------------------------------------------------------------------------
# Running the checks
# --------------------------------------------------------------------------


def pr_body(command, repo):
    words = split_words(command)
    body = flag_value(words, "--body", "-b", *(("--description", "-d") if "glab" in words else ()))
    if body is not None:
        return body
    path = flag_value(words, "--body-file", "-F")
    if path:
        try:
            return (Path(repo) / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    return None


def run_checks(repo, body=None, action="push"):
    policy_out, policy, _ = check.policy_findings(repo)
    if action == "issue":
        return policy_out + (check.report_findings(repo, body, policy) if body else [])
    diff_out, _ = check.diff_findings(repo, None)
    text_out = check.pr_findings(body, policy) + check.reference_findings(repo, body) if body else []
    return policy_out + diff_out + text_out


def summarize(findings, levels):
    lines = []
    for f in findings:
        if f.level in levels:
            line = f"- {f.level.upper()}: {f.message}"
            if f.quote:
                line += f' ("{check.short(f.quote, 140)}")'
            lines.append(line)
    return "\n".join(lines[:8])


HANDOFF_ACTIONS = ("pull request", "issue", "patch email")


def decide(repo, command, key=None, action=None, agent=False):
    """Return (decision, reason). decision is 'allow', 'ask' or 'deny'.

    `agent` is True when an AI agent is about to run the command (the Claude Code hook). Then a project rule that a
    person must submit the work hands the step to the person (ask) instead of letting the agent send it. Git hooks
    pass False, because the person may be the one running git."""
    if os.environ.get("SARWAN_SKILL_GUARD", "").lower() in ("off", "0", "false"):
        return "allow", "guard turned off by SARWAN_SKILL_GUARD"
    if action is None:
        key, action = target_of(repo, command)
    if action is None:
        return "allow", "not a push or pull request"
    elsewhere = is_someone_elses(key, github_login())
    if elsewhere is False:
        return "allow", f"{key} is yours"
    body = pr_body(command, repo) if action in ("pull request", "issue") else None
    findings = run_checks(repo, body, action)
    level = check.worst(findings)
    where = key or "another project"
    if level == "stop":
        return "deny", (f"sarwan_skill: this {action} goes to {where}, and the project's rules say stop:\n"
                        f"{summarize(findings, ('stop',))}\nStop and tell the person.")
    handoff = next((f for f in findings if f.code == "flag-no-autonomous-agents"), None) \
        if agent and action in HANDOFF_ACTIONS else None
    if elsewhere and (level == "fix" or handoff):
        parts = []
        if handoff:
            parts.append(f"sarwan_skill: {where} wants a person, not an agent, to send this {action} "
                         f"(see {handoff.where}). Hand this step to the person: show them the branch and the text, "
                         "and let them decide whether to send it.")
        if level == "fix":
            parts.append(f"sarwan_skill found things to fix before this {action} goes to {where}:\n"
                         f"{summarize(findings, ('fix',))}")
        parts.append("Approve only if you, the person, have read this and want to send it.")
        return "ask", "\n".join(parts)
    return "allow", "checks passed"


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------


def claude_code_hook():
    try:
        data = json.load(sys.stdin)
        command = (data.get("tool_input") or {}).get("command", "")
        if not ACTIONS.search(command or ""):
            return 0
        repo = Path(data.get("cwd") or ".")
        m = re.search(r"(?:^|&&|;)\s*cd\s+(\S+)\s*&&", command)
        if m:
            repo = (repo / m.group(1).strip("'\"")).resolve()
        m = re.search(r"\bgit\s+-C\s+(\S+)", command)
        if m:
            repo = (repo / m.group(1).strip("'\"")).resolve()
        decision, reason = decide(repo, command, agent=True)
    except Exception as exc:  # never break the person's session
        print(f"sarwan_skill guard skipped: {exc}", file=sys.stderr)
        return 0
    if decision == "allow":
        return 0
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                             "permissionDecisionReason": reason}}))
    return 0


def pre_push(name, url):
    top = check.git(Path.cwd(), "rev-parse", "--show-toplevel")
    repo = Path(top.strip()) if top else Path.cwd()
    try:
        key = dict(check.remote_keys(repo)).get(name) or key_from_url(url or name)
        decision, reason = decide(repo, f"git push {name}", key=key, action="push")
    except Exception as exc:
        print(f"sarwan_skill guard skipped: {exc}", file=sys.stderr)
        return 0
    if decision == "allow":
        return 0
    print(reason, file=sys.stderr)
    print(f"To push anyway (only if you, the person, decided to): {HOOKS['pre-push'][2]}", file=sys.stderr)
    return 1


def sendemail_validate(patch_file):
    counter = os.environ.get("GIT_SENDEMAIL_FILE_COUNTER")
    if counter and counter != "1":
        return 0  # the whole series was checked with its first email
    top = check.git(Path.cwd(), "rev-parse", "--show-toplevel")
    repo = Path(top.strip()) if top else Path.cwd()
    try:
        remotes = dict(check.remote_keys(repo))
        key = remotes.get("upstream") or remotes.get("origin")
        decision, reason = decide(repo, "git send-email", key=key, action="patch email")
    except Exception as exc:
        print(f"sarwan_skill guard skipped: {exc}", file=sys.stderr)
        return 0
    if decision == "allow":
        return 0
    print(reason, file=sys.stderr)
    print(f"To send anyway (only if you, the person, decided to): {HOOKS['sendemail-validate'][2]}", file=sys.stderr)
    return 1


def install(repo):
    repo = Path(repo).resolve()
    hooks_dir = check.git(repo, "rev-parse", "--git-path", "hooks")
    if hooks_dir is None:
        print(f"not a git repository: {repo}", file=sys.stderr)
        return 2
    script = Path(__file__).resolve().as_posix()
    failed = 0
    for name, (args, when, _) in HOOKS.items():
        hook = (repo / hooks_dir.strip()).resolve() / name
        if hook.exists() and MARK not in hook.read_text(encoding="utf-8", errors="replace"):
            print(f"{hook} already exists and is not ours. Add this line to it yourself:\n"
                  f'python3 "{script}" {args} || exit 1', file=sys.stderr)
            failed = 1
            continue
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(f"#!/bin/sh\n{MARK} {name} hook: checks a contribution {when}.\n"
                        "if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi\n"
                        f'exec "$PY" "{script}" {args}\n', encoding="utf-8")
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"installed {hook}")
    return failed


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] == "claude-code":
        return claude_code_hook()
    if argv[0] == "pre-push":
        return pre_push(argv[1] if len(argv) > 1 else "origin", argv[2] if len(argv) > 2 else "")
    if argv[0] == "sendemail-validate":
        return sendemail_validate(argv[1] if len(argv) > 1 else "")
    if argv[0] == "install":
        repo = argv[argv.index("--repo") + 1] if "--repo" in argv else "."
        return install(repo)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
