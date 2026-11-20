# The AI contribution policy block (for maintainers)

Your AI policy is written for people. Agents read it too, and they misread it. Paste this block into your `CONTRIBUTING.md` (or `AI_POLICY.md`) so every agent that follows sarwan_skill knows your rules exactly. People can read it as well: GitHub shows it as a small code block.

Keep your full policy in prose. The block is the short answer to the questions agents get wrong.

The easiest way to write both is to ask your agent to "write an AI contribution policy for this project": the **ai-policy-writer** skill in this repository asks you six questions and writes the prose, the block, a PR template item and an AGENTS.md note.

## Copy this

~~~markdown
## AI contributions

```ai-contribution-policy
version: 1
ai-assistance: allowed        # allowed | ask-first | not-accepted
disclosure: assisted-by       # assisted-by | pr-description | both | not-needed
issue-first: yes              # yes = only work on an issue a maintainer has accepted
agent-opened-prs: no          # no = a person must review and open every pull request
human-written-text: no        # yes = PR descriptions, issues and comments must be written by a person
details: https://example.org/your-full-policy
```
~~~

Change the values to match your project, and delete the `details` line if your policy is all in this file.

## What each line means

| Key | Values | Meaning |
| --- | --- | --- |
| `version` | `1` | The format version. |
| `ai-assistance` | `allowed`, `ask-first`, `not-accepted` | Whether you accept contributions made with AI help. `ask-first` means "talk to us before you start". |
| `disclosure` | `assisted-by`, `pr-description`, `both`, `not-needed` | How contributors should say AI helped. `assisted-by` means an `Assisted-by:` trailer in the commit message. |
| `issue-first` | `yes`, `no` | `yes` means no pull request without an issue a maintainer has accepted. |
| `agent-opened-prs` | `yes`, `no` | `no` means an agent may help, but a person reviews and opens every pull request. |
| `human-written-text` | `yes`, `no` | `yes` means descriptions, issues and comments must be written by a person, not generated. |
| `details` | a URL | Where the full policy lives, if it is somewhere else. |

Unknown keys and values are reported as problems, so typos don't fail silently. The block wins over anything the checker guesses from your prose.

## A badge, if you want one

Pick the line that matches your `ai-assistance` value and link it to your policy:

```markdown
[![AI contributions: allowed](https://img.shields.io/badge/AI_contributions-allowed-brightgreen)](CONTRIBUTING.md#ai-contributions)
[![AI contributions: disclose](https://img.shields.io/badge/AI_contributions-disclose-blue)](CONTRIBUTING.md#ai-contributions)
[![AI contributions: ask first](https://img.shields.io/badge/AI_contributions-ask_first-yellow)](CONTRIBUTING.md#ai-contributions)
[![AI contributions: not accepted](https://img.shields.io/badge/AI_contributions-not_accepted-red)](CONTRIBUTING.md#ai-contributions)
```

## Check it

From your repository:

```bash
python3 path/to/sarwan_skill/skills/sarwan-skill/scripts/check.py policy
```

It prints what an agent will understand from your files, and any problems with the block.

## Why a block and not a new file format

You don't need another file in your repository, or a new standard to adopt. It lives inside the document you already have, a person can read it, and it takes a minute to add. If a better shared format appears, this project will support it.
