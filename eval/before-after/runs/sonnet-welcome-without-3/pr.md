## What does this change?

`parse_size` matched the fractional part of a number but dropped it, so `"1.5k"` became `1k` (1024). The regex now captures the whole number and it is converted with `fractions.Fraction`, so the scaling is exact (no float rounding). The result is still an `int`; any leftover fraction of a byte is truncated, as before.

## Which issue does it fix?

Fixes #12

## How was it tested?

Added `test_decimals` (`1.5k` -> 1536, `0.5M` -> 524288, `2.0k` -> 2048). Ran the full suite with `python3 -m unittest discover -s tests`; all tests pass.

## AI assistance

Claude Code helped write the fix and test. I reviewed and tested the change. The commit carries an `Assisted-by: Claude Code` trailer per CONTRIBUTING.md.
