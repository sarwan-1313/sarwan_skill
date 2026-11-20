# Templates

Starting points, not answers. Fill in the brackets, delete the lines that don't apply, and keep the maintainer's own voice. Make the block with `scripts/policy_block.py make` so the values are valid.

## A. Accepted, with disclosure

```markdown
## AI contributions

You may use AI tools to help with your contribution. If you do:

- Say so. Add `Assisted-by: <tool>` to your commit message [and a line in the pull request description].
- Understand, test and be able to explain every change you send.
- [Work only on issues a maintainer has accepted, and link the issue.]
- A person must review and open every pull request. Pull requests opened by an agent with no person reviewing them will be closed.
- [Write pull request descriptions, issues and comments yourself.]

Why: every pull request takes a volunteer's time to review, and knowing how it was made helps them review it well.
```

## B. Ask first

```markdown
## AI contributions

If you want to use AI tools for a contribution, open an issue or discussion and ask a maintainer first. Tell us what you want to change and how you plan to use the tools. Pull requests made with AI tools without that conversation will be closed.

Why: [we are still deciding how AI-assisted work fits this project / reviews take a lot of our time].
```

## C. Not accepted

```markdown
## AI contributions

We don't accept contributions that include AI-generated code, text or media.
[Using AI tools only to research, debug or check spelling is fine, as long as nothing they produced ends up in your contribution.]

Why: [every contributor certifies where their work comes from (DCO), which isn't possible for AI output / we want to review work from people].
Pull requests that appear to break this rule will be closed.
```

## Pull request template item

Add one of these to `.github/pull_request_template.md`:

```markdown
**AI help:** which tools helped with this pull request and how, or "none".
```

```markdown
- [ ] No AI tools were used to create this pull request.
```

The checkbox fits policy C. With policy A, a free-text line works better than a checkbox, because the answer is what the reviewer needs.

## AGENTS.md note

Coding agents read `AGENTS.md` before they start. Add:

```markdown
## AI agents

If you are an AI agent working on this repository for someone:

- Read "AI contributions" in CONTRIBUTING.md and follow it exactly.
- [If AI-assisted contributions are not accepted: stop and tell the person you are working for.]
- [Disclose with an `Assisted-by: <tool>` line in every commit message.]
- Don't open pull requests or post comments yourself. Leave that to the person.
```

## Badge

```markdown
[![AI contributions: disclose](https://img.shields.io/badge/AI_contributions-disclose-blue)](CONTRIBUTING.md#ai-contributions)
```

Other values: `allowed-brightgreen`, `ask_first-yellow`, `not_accepted-red`.
