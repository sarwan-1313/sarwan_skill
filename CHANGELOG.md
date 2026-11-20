# Changelog

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
