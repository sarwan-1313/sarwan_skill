# Changelog

## 1.4.0

- **Handoff.** When a project wants a person, not an agent, to submit ("AI agents must not open pull requests", "a human must be the one to submit", `agent-opened-prs: no`), the Claude Code guard now pauses `gh pr create`, `gh issue create` and patch emails and asks you, quoting the rule. Git hooks don't do this, since there the person may be the one running git. These rules are also found outside AI sections and in `AGENTS.md`.
- **Better ban reading**, after running the guard on 16 projects it had never seen. A pull request template that makes every contributor certify no AI was used now counts as a ban, and "No LLM, AI or agent assisted contributions are allowed" is no longer read as permission. "Coordinated disclosure" in a security note and "disclosure does not make it acceptable" no longer count as disclosure rules. "Have not included" and "merged" are now recognized, and a dedicated AI policy file that says no wins over an older template.
- **Refuse and handoff evaluation** on 78 real projects ([eval/refuse-handoff/](eval/refuse-handoff/)): 25/25 bans blocked and 10/10 handoffs on the development set, and no project that allows AI was blocked. On the unseen projects the first run blocked 5/10 bans and paused the rest; after the fixes above it blocks 9/10 and hands off 3/3.
- `plugin.json` now declares the one host the plugin reaches, `api.github.com`, through the GitHub CLI. It passes `claude plugin validate --profile directory --strict`.
- 6 new tests, 110 in all.

## 1.3.0

- **Other issues to work on.** When `check.py issue <number>` finds the issue taken (closed, assigned, claimed, not ready, already being fixed, or a good first issue the project keeps for newcomers), it now lists up to five other open, unassigned issues to offer the person, accepted ones first. It suggests nothing when the project doesn't accept AI help at all.
- **Changelog entries.** `check.py diff` now notices when a project records changes as separate files (towncrier, changesets, reno, scriv or a `changelog.d` folder) or asks for a CHANGELOG line in its contributing guide or PR template, and flags a code change that has none. It is a FIX when the project's CI checks for it, so the guard asks before the push.
- **CLAs.** `check.py policy` now finds when a project needs a signed Contributor License Agreement (in its guides, its PR template, a CLA bot or a CLA check in CI) and reminds the agent that only the person can sign it. Wording like "no CLA is required" doesn't count.
- 15 new tests, 104 in all. Tried on pip, changesets, Click, Requests and Python Fire.

## 1.2.0

- **Fact check.** `check.py pr` (and `all --pr`) now flags files, line numbers and functions that a pull request description mentions but the repository doesn't have, before or after the change. It's a common sign of text written without reading the code.
- **Bug and security reports.** `check.py report <file>` checks a report before it is filed: made-up files, lines and functions, no way to reproduce it, no version, no expected result, speculative wording, filler, missing disclosure, a security report about to go public, and projects that don't accept AI-written issues.
- **The guard covers more ways to send work.** Patches sent by email (`git send-email`, `b4 send`), the way QEMU and the Linux kernel take them, and new issues (`gh issue create`, `glab issue create`). `guard.py install` now also adds a `sendemail-validate` git hook. Both were tested in a real Claude Code session.
- **Before and after.** `eval/before-after/` runs the same contribution task in Claude Code with and without the plugin and scores the results.

## 1.1.0

- **The guard.** With the Claude Code plugin, the checks run by themselves before `git push`, `gh pr create` or `glab mr create` to a repository you don't own. A project that doesn't accept AI help blocks the command; anything else to fix asks you first. Pushes to your own fork are not touched. `guard.py install` adds the same check as a git pre-push hook for any agent. Tested in a real Claude Code session.
- **Live GitHub checks** through the GitHub CLI, only when asked: `check.py issue <number>` (open, assigned, accepted, claimed, duplicate pull requests, your open pull requests) and `check.py policy --online` (a policy the organisation keeps in its `.github` repository).
- **New skill: ai-policy-writer.** For maintainers: shows what 189 real projects decided, asks six questions, writes the CONTRIBUTING section, the policy block, a PR template item, an AGENTS.md note and a badge, and checks the result the way contributing agents will read it.
- The checker warns when a project's written policy and its policy block disagree, and no longer reads code blocks as policy text.
- A demo GIF and `demo/slop_demo.sh`, which builds a typical slop contribution to try the checker on.

## 1.0.0

- The skill: five rules for agents contributing to projects someone else maintains.
- The checker: `policy`, `diff`, `pr` and `all`, standard library only, no network.
- The published AI policies of 189 projects, from a CC0 list.
- The ai-contribution-policy block for maintainers.
- An evaluation on 72 real projects (`eval/`).
