## What does this change?

`parse_size` ignored the fractional part of a number, so `"1.5k"` returned 1024 instead of 1536. The regex now captures the whole number, which is then multiplied exactly with `fractions.Fraction`. Whole numbers behave as before.

## Which issue does it fix?

Fixes #12

## How was it tested?

- `python3 -m unittest discover -s tests`: 8 tests pass.
- Added `test_decimal_units` (`"1.5k"` → 1536, `"1.5M"` → 1.5 MiB). It fails on the old code and passes with this change.
- Checked by hand: `"2k"`, `"1."`, `"0.5k"`, `"1.25 MiB"`, `"2.5 GB"` return the expected values; `"lots"` and `".5k"` still raise `ValueError`, as before.

## AI assistance

Used Claude Code (Haiku 5.5) to find the cause and draft the change and test. I read every line, reproduced the bug on the original code, and ran the test suite myself.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
