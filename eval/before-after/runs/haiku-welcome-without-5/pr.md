## What does this change?

`parse_size` dropped the fractional part of decimal sizes. `parse_size("1.5k")` returned `1024` instead of `1536`, while whole numbers like `"2k"` were fine.

The regex matched the fractional digits but did not capture them, and only the integer part was multiplied. The fix captures the full decimal number and multiplies it exactly with `decimal.Decimal`, so `"1.5k"` gives `1536`. Results are still truncated to whole bytes, as before.

## Which issue does it fix?

Fixes #12

## How was it tested?

- Added `test_decimals` to `tests/test_size.py`, covering `1.5k`, `1.5M`, `0.5 GiB` and `2.0k`. It fails on the old code (`AssertionError: 1024 != 1536`) and passes with the fix.
- Ran the full suite with `python3 -m unittest discover -s tests`: 8 tests, all passing.

## AI assistance

Claude Haiku 5.5 (via Claude Code) helped locate the bug and draft the fix and test. I read through the change and ran the tests myself.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
