---
name: ai-policy-writer
description: Helps open-source maintainers decide and write their project's AI contribution policy, using what 189 real projects decided. Asks a few questions, then writes a short policy for CONTRIBUTING.md, an ai-contribution-policy block that coding agents read exactly, a pull request template item, an AGENTS.md note and a badge, and checks that agents will understand it as intended. Use when a maintainer wants an AI policy, rules for AI-generated pull requests or issues, or help with a flood of low-quality AI contributions ("AI slop").
license: MIT
metadata:
  author: sarwan-1313
  version: "1.1.0"
---

# AI policy writer

You are helping a maintainer decide how their project handles AI-assisted contributions, and write it down so that people and coding agents read it the same way. The decision is the maintainer's. Stay neutral: don't push them toward accepting or refusing AI help.

## 1. Look before you ask

- Read the README, CONTRIBUTING (and any contributing docs), the PR and issue templates, AGENTS.md and LICENSE. Note any AI wording already there, and whether the project uses DCO sign-off or a CLA.
- Run `python3 <this-skill-folder>/scripts/policy_stats.py` to see what real projects decided, with links. `--list no` (or `yes`, `with-conditions`) lists every project in a group.

## 2. Ask once, with defaults

Ask these in one message. For each, give your suggested default for this project and one line on the tradeoff.

1. Accept AI-assisted contributions? `allowed`, `ask-first` or `not-accepted`.
2. How should contributors disclose it? An `Assisted-by:` trailer, the PR description, both, or not needed.
3. Only for issues a maintainer has accepted first? This cuts drive-by pull requests.
4. May an agent open pull requests with no person reviewing them? Most projects say no.
5. Must PR descriptions, issues and comments be written by a person?
6. Anything special: security reports, good first issues, docs or translations, licence or copyright concerns.

If they ask what you would choose, base it on the project's size, review capacity, licence and community, and say so.

## 3. Write it

Start from `assets/templates.md`.

- A short `## AI contributions` section for CONTRIBUTING.md (or AI_POLICY.md if they prefer). Rules first, in plain words, then one or two lines of why. Under 200 words.
- The block, made with `python3 <this-skill-folder>/scripts/policy_block.py make --ai-assistance … --disclosure … --issue-first … --agent-opened-prs … --human-written-text …`. Paste it under the prose.
- One disclosure item for the PR template.
- A short `## AI agents` note in AGENTS.md. Agents read it first.
- A README badge, if they want one.

The prose and the block must say the same thing.

## 4. Check that it reads right

- `python3 <this-skill-folder>/scripts/policy_block.py check CONTRIBUTING.md` must pass.
- If the sarwan-skill skill is installed next to this one, run `python3 <this-skill-folder>/../sarwan-skill/scripts/check.py policy --repo <repo>`. It reads the files the way contributing agents will. It must report the stance the maintainer chose and no "prose and block disagree" warning. If it misreads the prose, the wording is ambiguous: make it plainer.

## 5. Hand it over

- Show the changes as a diff. The maintainer edits and approves. Don't commit, push or open a pull request unless they say so.
- Suggest telling contributors: a pinned issue or discussion, and a link from the README.

## Good to know

- Projects that use a DCO or a strong copyleft licence often give copyright as the reason for not accepting AI-generated code (QEMU, Gentoo). If the project uses a DCO, mention it, without giving legal advice.
- A policy nobody finds doesn't work. GitHub points new contributors to CONTRIBUTING.md, so put it there or link it from there.
- Keep it short. A long policy is skimmed by people and misread by agents.
