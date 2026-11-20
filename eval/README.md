# Evaluation

Two questions:

- **Does the skill change what an agent does?** See [before-after/](before-after/): the same contribution task in Claude Code, with and without sarwan_skill.
- **How well does `check.py policy` read real projects' AI policies?** This page.

`projects.tsv` lists 72 projects that publish an AI contribution policy. Each one has a label from the public [open-source AI contribution policies](https://github.com/melissawm/open-source-ai-contribution-policies) list: AI-assisted contributions accepted (`yes`, `with-conditions`) or not accepted (`no`). `run.py` fetches only each project's documentation, runs the policy reader **without** the built-in list of known policies, and compares.

- **Right:** the list says no and the reader says `not-accepted`, or the list says yes and the reader says accepted (`allowed`, `disclose` or `restricted`).
- **Missed:** the reader says `unclear` or `silent`. The checker then tells the agent to show the person the lines and ask, so a miss is slower but not dangerous.
- **Wrong:** the reader gives the opposite answer.

```bash
python3 eval/run.py            # needs git and access to github.com
python3 eval/run.py --set round2
```

## Results

The projects were used in three groups, in this order.

| Group | Projects | How it was used | First run | Now |
| --- | --- | --- | --- | --- |
| `tuning` | 16 | Read while writing the patterns | — | 14 right, 2 missed |
| `round1` | 24 | Not seen before; failures were then fixed | 17 right, 3 missed, 3 wrong | 24 right |
| `round2` | 32 | Not seen before; run once with no changes | 27 right, 4 missed, 1 wrong | 32 right |

- The two `tuning` misses, Flask and Servo, publish their policies on a website rather than in the repository. The reader can't see those, but the built-in list of known policies stops the agent for both.
- `round2` is the fairest number: **27 of 32 right, 4 "unclear, ask the person", 1 wrong**, on projects the patterns had never seen. The wrong one was a ban written inside a pull request template checkbox.
- Every failure from `round1` and `round2` is now a unit test in `tests/test_check.py`.

## Limits

- The labels come from a community list that says its classification is "a general guide", not the source of truth. "Right" means the reader agrees with that list.
- New policies will use wordings these patterns haven't seen. That's why the checker always quotes the lines it relied on and the skill tells the agent to read them.
- The fetch only checks out documentation files, so a policy kept somewhere unusual in a repository may be missed here but found in a full clone.
