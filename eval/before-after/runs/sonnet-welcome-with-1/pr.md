## What does this change?

`parse_size` now keeps the fractional part of decimal sizes, so `parse_size("1.5k")` returns 1536 instead of 1024. The regex matched the digits after the point but did not capture them. The number is now parsed with `Fraction` to avoid float rounding, then truncated to an int.

## Which issue does it fix?

Fixes #12

## How was it tested?

Reproduced the bug first (`parse_size("1.5k")` gave 1024). Added `test_decimals` in `tests/test_size.py`. Ran `python3 -m unittest discover -s tests`: 8 tests, all OK.

## AI assistance

I used Claude Code to help write the fix and tests. I reviewed and ran every change. Commit has an `Assisted-by: Claude Code` trailer.
