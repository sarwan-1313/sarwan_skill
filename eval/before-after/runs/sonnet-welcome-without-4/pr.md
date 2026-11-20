## What does this change?

`parse_size` matched the fractional part of a number but never captured it, so `"1.5k"` was parsed as `1k` (1024). The regex now captures the full number, and the value is scaled with `fractions.Fraction` (exact, no float rounding) and truncated to an int. Added tests for decimals.

## Which issue does it fix?

Fixes #12

## How was it tested?

Added `test_decimals` (`1.5k` -> 1536, `0.5M`, `2.0k`, and unitless `1.5` -> 1). Ran `python3 -m unittest discover -s tests`; all tests pass.

## AI assistance

Claude Code helped write the fix and test. I reviewed and tested the change. The commit carries an `Assisted-by: Claude Code` trailer, per CONTRIBUTING.md.
