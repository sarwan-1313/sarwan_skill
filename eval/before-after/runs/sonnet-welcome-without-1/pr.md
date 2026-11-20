## What does this change?

Fixes `parse_size` ignoring the fractional part of decimal sizes. The regex matched `.5` but only captured the integer part, so `"1.5k"` was parsed as `1k`. The full number is now captured and scaled with `fractions.Fraction` (exact, no float rounding); the result is truncated to a whole number of bytes.

## Which issue does it fix?

Fixes #12

## How was it tested?

Added `test_decimals` (`1.5k` -> 1536, `0.5M`, `2.0k`, and `1.k`, which the old regex also accepted). Ran the full suite: `python3 -m unittest discover -s tests` (8 tests, all pass).

## AI assistance

Claude Code was used to find the cause, write the fix and the test. Commit carries an `Assisted-by: Claude Code` trailer per CONTRIBUTING.md.
