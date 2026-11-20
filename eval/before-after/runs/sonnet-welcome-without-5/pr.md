## What does this change?

`parse_size` ignored the fractional part of decimal sizes: the regex matched `.5` in `"1.5k"` but didn't capture it, so only `1` was used and the result was 1024. The full number is now captured and multiplied using `fractions.Fraction`, so the result is exact (no float rounding) and truncated to an int. Whole numbers behave as before.

## Which issue does it fix?

Fixes #12

## How was it tested?

Added `test_decimals` in `tests/test_size.py` (`1.5k` -> 1536, `1.5M`, `0.5 KiB` -> 512, `2.k` -> 2048). Ran the full suite with `python3 -m unittest discover -s tests`; all tests pass.

## AI assistance

Claude Code helped find the cause, write the fix and the test. I reviewed the change and ran the tests.
