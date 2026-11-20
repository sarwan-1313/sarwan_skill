## What does this change?

`parse_size` captured only the integer part of the number, so the fractional part was dropped (`"1.5k"` -> 1024). The regex now captures the whole number, and the multiplication uses `fractions.Fraction` so results are exact (no float rounding). Results are still returned as `int` (any fractional byte is truncated, e.g. `"1.5"` -> 1).

## Which issue does it fix?

Fixes #12

## How was it tested?

Added cases to `tests/test_size.py` for `"1.5k"` (1536), `"1.5M"`, and `"0.5 KiB"` (512). Full suite passes:
`python3 -m unittest discover -s tests`

## AI assistance

Claude Code was used to diagnose and write the fix and tests. The change was reviewed and tested by me before submitting. Commit carries an `Assisted-by: Claude Code` trailer.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
