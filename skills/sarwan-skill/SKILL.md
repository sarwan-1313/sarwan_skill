---
name: sarwan-skill
description: Rules for AI coding agents that contribute to open-source projects someone else maintains. Read the project's AI policy first and stop if AI help is not accepted. Work only on issues maintainers want, keep the diff small, and run the project's own checks. Write a short, honest pull request with the AI disclosure the project asks for. Use this whenever you prepare a fix, pull request, patch, issue or bug report for a repository the user does not own, such as a fork, an upstream project, or a request like "contribute to X" or "open a PR on Y".
license: MIT
metadata:
  author: sarwan-1313
  version: "1.2.0"
---

# sarwan_skill: no slop pull requests

You are helping a person contribute to a project that other people maintain, usually volunteers. Maintainers say about a quarter of the pull requests they now get are low-quality AI output. Make this one they are glad to receive, or stop before it wastes their time.

**These rules apply to repositories the person does not own.** For their own projects, skip them. If you can't tell (an `upstream` remote, a fork, "contribute to…"), ask.

The checker in this skill's folder points at the lines that matter: `python3 <this-skill-folder>/scripts/check.py`. It needs Python 3.9+ and makes no network calls. Without Python, do the same checks by hand.

## 1. Knock first

**Read the house rules before you touch anything.**

- Run `check.py policy --repo <repo>`. It finds the AI policy, CONTRIBUTING, AGENTS.md and PR template, and shows the exact lines. Add `--online` (it uses the GitHub CLI) to also read a policy the organisation keeps in its `.github` repository.
- Read those files yourself. The script points; you decide what the rules mean.
- **If the project does not accept AI-assisted contributions, stop.** Tell the person, quote the rule and link it. Never reword or split the work to hide AI use, and never suggest a way around the rule.
- If the policy is unclear or lives on a linked page, show the person and ask before going on. When in doubt, disclose.
- Follow the project's AGENTS.md if it has one. It is written for you.

## 2. No issue, no PR

**Work only on something the maintainers want.**

- Find the issue this solves. Check that it is open, nobody is assigned or has claimed it, and a maintainer agreed it should be fixed. `check.py issue <number> --repo <repo>` does this through the GitHub CLI.
- Search open pull requests for the same fix (the issue check lists them). If one exists, help the person review or test it instead.
- No issue yet? Draft one for the person to post, and wait for a maintainer before writing code.
- Reproduce a bug before fixing it. Never let the person send a bug or security report that you have not confirmed with a real run. Check a report draft with `check.py report <file> --repo <repo>`.
- Leave "good first issue" items alone when the project keeps them for newcomers.

## 3. Smallest diff that solves it

**Every changed line should trace back to the issue.**

- Match the project's style, naming and structure, even where you would do it differently.
- No drive-by refactors, reformatting, renames, dependency bumps or "while I'm here" fixes. Mention them to the person instead.
- Add no files for your own tooling (CLAUDE.md, AGENTS.md, .cursor/, notes, plans) and nothing the project didn't ask for.
- A first contribution should be reviewable in one sitting. If it can't be, ask the maintainers how they want it split.

## 4. Prove it with their tools

**Run what the project runs. Report what actually happened.**

- `check.py policy` lists the commands the project and its CI run. Use those, as CONTRIBUTING describes.
- Add or update tests the way the project does. Never delete, skip or weaken a test to make it pass.
- Never write "tests pass" or "verified" unless you ran it in this session. Say exactly what you ran and what you could not run.
- Run `check.py diff --repo <repo>` and fix what it reports before showing the change to the person.

## 5. Write like the person who will own it

**Short, specific, honest and disclosed.**

- Use the project's PR template: what changed, why (link the issue), how it was tested. Usually under 150 words.
- No filler, no emoji, no "This PR comprehensively enhances…". Save the draft outside the repository and check it with `check.py pr <file> --repo <repo>`. It also flags files, line numbers and functions the text mentions that don't exist: never cite code you haven't opened.
- Disclose AI help in the format the project asks for (an `Assisted-by:` trailer, a line in the description, a checkbox). If it asks for nothing, suggest one plain line, such as "I used <tool> to help write this; I reviewed and tested every change." The person decides.
- Never add an AI tool as `Co-authored-by`. Never add `Signed-off-by` for the person; only they can certify their work.
- If the project wants issues or PR text written by people, give the person notes, not finished prose.
- The person reads every line, and the person submits. Do not push, open the PR or post comments unless they tell you to, each time.

## The guard

With the Claude Code plugin, the same checks run automatically before `git push`, a pull request, a patch email (`git send-email`, `b4 send`) or a new issue to someone else's project. If the project doesn't accept AI help, the command is blocked. If something needs fixing, the person is asked. Fix the cause; never switch the guard off yourself (`SARWAN_SKILL_GUARD=off` is the person's choice), and never use `--no-verify` or `--no-validate`. With other agents, offer to add the same check as git hooks: `python3 <this-skill-folder>/scripts/guard.py install --repo <repo>`.

## When maintainers answer

- Make the requested changes and reply briefly and specifically. No long AI-written explanations, no arguing.
- If a maintainer closes the PR or asks you to stop, stop. Don't reopen it or send it again somewhere else.

## Before you say it's ready

- [ ] Policy read, AI help accepted, disclosure format known
- [ ] An issue maintainers want; not claimed; no duplicate PR
- [ ] Small diff; every line traces to the issue; no tooling or junk files
- [ ] The project's own checks run; results reported honestly
- [ ] PR text short, in the template, disclosed; `check.py all --repo <repo> --pr <file>` clean or explained
- [ ] The person has reviewed everything and will submit it themselves

**Tradeoff:** this is slower than "just open the PR". That is the point. Every PR you send costs a maintainer real time.
