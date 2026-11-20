## What does this change?

`parse_size` now keeps the fractional part of the number, so `parse_size("1.5k")` returns 1536 instead of 1024. The regex captured only the integer digits; it now captures the whole number, and the result is computed with `fractions.Fraction` (exact, no float rounding) and truncated to an int. Added a `test_decimals` test.

## Which issue does it fix?

Fixes #12

## How was it tested?

Ran `python3 -m unittest discover -s tests`: 8 tests pass, including the new decimal cases (`1.5k`, `0.5M`, `2.GiB`).

## AI assistance

I used Claude Code to help write this fix and the test; I reviewed and ran every change. The commit has an `Assisted-by: Claude Code` trailer.
