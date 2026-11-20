# Examples

Common ways an agent's contribution to someone else's project goes wrong, and what it does with sarwan_skill instead. For measured results, see [Before and after](README.md#before-and-after). Checker output is real (trimmed and wrapped to fit): QEMU and Flask from copies of their repositories, the rest from a small demo project with a typical slop contribution.

---

## 1. The project doesn't accept AI-assisted work

**You:** "There's a typo in QEMU's docs. Fix it and send a patch."

**Without the skill:** the agent fixes the typo, writes the commit and drafts the patch email. QEMU declines any contribution it believes includes AI-generated content, so the patch is a waste of a maintainer's time and a mark against you.

**With the skill:** the agent runs the policy check first and stops.

```
== Project rules
  STOP   This project does not accept AI-assisted contributions. Stop and tell the person, quoting the
         rule. Do not reword the change to hide AI use.
         at docs/devel/code-provenance.rst:293
         "**Current QEMU project policy is to DECLINE any contributions which are believed to include or
         derive from AI generated content. This includes ChatGPT, Claude, Copilot, Llama and …"
```

> QEMU does not accept AI-assisted contributions (docs/devel/code-provenance.rst). I haven't changed anything. If you'd like to fix the typo, you can make the one-line change yourself, or report it to the qemu-devel list in your own words.

The same happens when the policy lives on a website. Flask's repository says nothing about AI, but Pallets publishes a policy, and the checker knows it:

```
  STOP   A shared list of project AI policies (snapshot 2026-11-02) says Pallets does not accept
         AI-generated contributions. Read the policy: https://palletsprojects.com/contributing/llm-ai
         Stop and confirm with the person.
```

---

## 2. No issue, no PR

**You:** "Add a `--json` flag to this CLI and open a PR."

**Without the skill:** a 300-line pull request nobody asked for. It conflicts with a maintainer's plan, duplicates an open PR, or gets closed because the project requires an accepted issue first.

**With the skill:**

```
  CHECK  Wants an issue first: work only on an issue maintainers have accepted, and link it.
         at CONTRIBUTING.md:5
```

> The project wants an accepted issue before any PR. I searched: there's no issue for a `--json` flag, and no open PR adding one. Here's a short issue draft for you to post. I'll wait for a maintainer to reply before writing code.

---

## 3. The drive-by cleanup

**You:** "Fix the crash when the input is empty."

**Without the skill:** the agent fixes the crash, then "improves" the file: it reformats it, renames two variables, bumps a dependency, adds its own `CLAUDE.md` and a `PLAN.md`, and installs packages with npm in a project that uses yarn. The diff is 23 files for a two-line fix.

**With the skill:** the diff check catches the extras before you see them.

```
== Your change
  FIX    CLAUDE.md (added) is a file for your own AI tooling. It does not belong in their repository:
         leave it out of the change.
  FIX    PLAN.md (added) looks like working notes or a plan. Leave it out unless the issue asked for it.
  FIX    Added package-lock.json, but the project uses yarn.lock. Use the project's package manager and
         drop the new lockfile.
  FIX    Only whitespace or formatting changed in src/util.py. Revert it unless the issue asks for
         reformatting.
```

The final diff is the two lines that fix the crash, plus a test.

---

## 4. "All tests pass"

**Without the skill:** the test fails, so the agent adds `@pytest.mark.skip`, or loosens the assertion, then reports "all tests pass".

**With the skill:**

```
  FIX    Added a skipped or disabled test in tests/test_parse.py. Never skip a test to make it pass;
         if it is truly needed, explain why in the PR.
         "@pytest.mark.skip"
  CHECK  1 more assertion line(s) removed than added in tests/test_parse.py. Make sure no test was
         weakened to make it pass.
```

> The existing test fails with my change because empty input now returns `[]` instead of `[""]`. That's the behavior the issue asks for, so I updated the expectation and said so in the PR. Ran: `pytest tests/test_parse.py` (3 passed). I could not run the Windows CI job locally.

---

## 5. The pull request description

**Without the skill:**

```markdown
## 🚀 Summary
This PR introduces a comprehensive and robust fix that seamlessly improves parsing. ✨

## ✅ Changes
- Leverages best practices for empty input 🎉
```

```
== Pull request text
  FIX    4 emoji. Drop them; they read as generated text.
  FIX    Generic filler words: comprehensive, robust, seamless, leverage, best practices. Say the
         specific thing instead.
  FIX    Says nothing about testing. State exactly what you ran and what you could not test.
  FIX    The project asks for AI disclosure and this description has none. Add it in the project's format.
  CHECK  No linked issue. Link the issue this solves (for example 'Fixes #123').
```

**With the skill:**

```markdown
Fixes #214.

`parse("")` returned `[""]`, so callers treated empty input as one empty field. It now returns `[]`.
I updated the existing test that expected the old behavior.

Tested: `pytest tests/test_parse.py` (3 passed). Not tested on Windows.

I used Claude Code to help write this; I reviewed and tested every change.
```

---

## 6. Commit trailers

**Without the skill:** `Co-Authored-By: Claude <noreply@anthropic.com>` on every commit. Many projects close pull requests that list an AI tool as an author (attrs and requests say so), and projects that use the Developer Certificate of Origin need the person's own `Signed-off-by`.

**With the skill:**

```
  FIX    Commit d44505d lists an AI tool as Co-authored-by. Remove it and disclose the way the project
         asks (often an `Assisted-by:` line or a PR note).
  CHECK  The project uses Signed-off-by (DCO). Only the person can add their own sign-off; never add
         it for them.
```

The commit ends with the trailer the project asked for, for example `Assisted-by: Claude Code`, and the person adds their own sign-off.

---

## 7. When the maintainer answers

**Maintainer:** "Thanks, but we'd rather not add this option."

**Without the skill:** a 400-word reply explaining why the option is valuable, or the same PR opened again with a different title.

**With the skill:** "Understood, thanks for looking." The PR stays closed.

---

## 8. The guard catches what the agent forgot

**You:** "Looks good, open the pull request."

**Without the guard:** the agent runs `gh pr create`, and every problem above lands in the maintainer's queue.

**With the Claude Code plugin:** the command stops before it runs, and you are asked first:

```
sarwan_skill found things to fix before this pull request goes to github.com/tinyparse-org/tinyparse:
- FIX: CLAUDE.md (added) is a file for your own AI tooling. It does not belong in their repository:
  leave it out of the change.
- FIX: Added a skipped or disabled test in tests/test_parse.py. Never skip a test to make it pass;
  if it is truly needed, explain why in the PR. ("@pytest.mark.skip")
- FIX: Commit d8aad1d lists an AI tool as Co-authored-by. Remove it and disclose the way the project
  asks (often an `Assisted-by:` line or a PR note).
Approve only if you have read them and want to send it anyway.
```

For a project that doesn't accept AI help, the command is blocked outright. That includes patches sent by email (`git send-email`, `b4 send`) and new issues (`gh issue create`). In a real Claude Code session, the agent then reported:

> The command didn't run. A pre-tool hook blocked it with this message: "sarwan_skill: this patch email goes to github.com/tinyparse-org/tinyparse, and the project's rules say stop: STOP: This project does not accept AI-assisted contributions. Stop and tell the person, quoting the rule. Do not reword the change to hide AI use. ("We do not accept contributions that include code or text generated by AI tools (such as Copilot, ChatGPT or Claude)…")"
>
> I stopped there, as you asked, and no email was sent.

---

## 9. A maintainer writes the rules

**Maintainer:** "We keep getting AI pull requests nobody tested. Write an AI contribution policy for this project."

**Without the skill:** a 900-word essay on AI ethics that nobody reads, and agents still guess.

**With ai-policy-writer:** the agent first shows what real projects decided:

```
What 189 open-source projects with a published AI policy decided

  Do not accept AI-assisted contributions        102  (54%)  e.g. QEMU, Gentoo Linux, Zig, Servo, Pallets, Bevy
  Accept them                                     78  (41%)  e.g. Linux Kernel, LLVM, curl, Django, NumPy, Kubernetes
  Accept them only with extra conditions           9  (5%)  e.g. NetBSD, Borgmatic, dlt, MDAnalysis, ...

Careful: this list is made of projects that chose to publish a policy, and it over-represents bans.
- Of 1,000 popular GitHub repositories, 118 had an AI contribution policy. Of those, 78% accept AI-assisted
  contributions and 22% discourage them; 51% require disclosure and 74% require human oversight.
```

Then it asks six questions, each with a suggested answer, writes a short section for CONTRIBUTING.md with the block underneath, and checks it the way contributing agents will read it:

```
== Project rules
  CHECK  AI help is accepted with disclosure. Disclose with an `Assisted-by:` trailer in the commit message.
  CHECK  Wants an issue first: work only on an issue maintainers have accepted, and link it.
  CHECK  No autonomous agents: a person drives the work and submits it.
```

If the prose had said one thing and the block another, the check would have said so.

---

## 10. A bug report about code that doesn't exist

**You:** "I think there's a security bug in tinyparse's size parsing. Write it up so I can file it."

**Without the skill:** a confident report, filed in public, about `_parse_decimal_fraction()` at `tinyparse/size.py:120`. Neither exists: the file has 23 lines. The maintainer spends an evening proving it's wrong.

**With the skill:** the agent reproduces the bug first, then checks its draft with `check.py report`, which reads the report against the repository:

```
== Report
  FIX    No way to reproduce it. Give exact steps or a minimal script, and the output you got.
  FIX    Points at line 120 of tinyparse/size.py, but the file has 23 lines. Check the line number.
  FIX    Mentions tinyparse/units.py, but there is no such file in this repository.
  FIX    Mentions _parse_decimal_fraction(), but `_parse_decimal_fraction` appears nowhere in this repository.
  CHECK  Speculative wording ("could potentially…"). Show it happening; maintainers can't act on a maybe.
  CHECK  This reads like a security report. Send it the private way the project asks, not as a public issue.
```

The same fact check runs on pull request descriptions. With the plugin, the guard runs it before `gh issue create`, too.
