# Contributing to sarwan_skill

Thanks for helping. This project follows its own rules, so the short version is: read [the skill](skills/sarwan-skill/SKILL.md) and do what it says.

## AI contributions

AI-assisted contributions are welcome. Say how AI helped in the pull request description, and make sure you understand and have tested every line. Open an issue first for anything bigger than a small fix, so we can agree on it before you spend time.

```ai-contribution-policy
version: 1
ai-assistance: allowed
disclosure: pr-description
issue-first: yes
agent-opened-prs: no
human-written-text: no
```

## Good first contributions

- **A missed rule.** If the checker misreads a real project's AI policy, open an issue with the project, the file and the line. These reports make the checker better for everyone.
- **A new known policy.** The list of known project policies comes from [open-source-ai-contribution-policies](https://github.com/melissawm/open-source-ai-contribution-policies) (CC0). Add new projects there first, then we refresh our copy with `tools/build_known_policies.py`.
- **A false alarm.** If `check.py diff` or `check.py pr` flags something that is fine, show the case in an issue.

## Making a change

1. Keep the change small and focused on one issue.
2. Run the tests: `python3 -m unittest discover -s tests`. They need only Python 3.9+ and git.
3. Run the checker on your own change: `python3 skills/sarwan-skill/scripts/check.py all --base main`.
4. If you change what the checker prints, rebuild the demo with `python3 demo/make_gif.py` (needs Pillow).
5. Keep each `SKILL.md` short. Every line is read by an agent on every contribution, so a new rule has to earn its place.

## Style

Plain words, short sentences, and messages that tell the reader what to do next.
