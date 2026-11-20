## What does this change?

`parse_size` dropped the fractional part of decimal sizes: the regex captured only the integer digits, so `"1.5k"` returned 1024 instead of 1536. The number is now captured in full and multiplied exactly with `Decimal` before truncating to an `int`. Whole numbers behave as before.

## Which issue does it fix?

Fixes #12

## How was it tested?

- Added `test_decimal_units` to `tests/test_size.py`, covering `"1.5k"`, `"0.5M"` and `"2.25k"`.
- Confirmed the new test fails on the original `size.py` and passes with the fix.
- Ran the whole suite: `python3 -m unittest discover -s tests` (8 tests, OK).

## AI assistance

Yes. I used Claude Code to find the cause and draft the change and test. I read and ran every line myself.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
