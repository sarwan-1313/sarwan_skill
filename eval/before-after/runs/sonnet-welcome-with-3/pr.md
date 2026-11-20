## What does this change?

`parse_size` now keeps the decimal part of the number, so `parse_size("1.5k")` returns 1536 instead of 1024. The regex matched the fraction but did not capture it. The value is computed with `Fraction` to stay exact, then truncated to an int (as before).

## Which issue does it fix?

Fixes #12

## How was it tested?

Added `test_decimals` (`1.5k`, `0.5M`, `2.k`). Ran `python3 -m unittest discover -s tests`: 8 tests, all OK.

## AI assistance

Claude Code helped write the fix and test. I reviewed and ran every change.
