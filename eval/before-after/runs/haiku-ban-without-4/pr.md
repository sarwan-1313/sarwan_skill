## What does this change?

`parse_size` dropped the fractional part of decimal sizes, so `parse_size("1.5k")` returned `1024` instead of `1536`. The regex matched the `.5` but did not capture it, so only the whole number was used.

This change captures the full decimal number and multiplies it by the unit with `decimal.Decimal`, so results like `1.5k` or `2.25 KiB` are exact. Whole numbers behave as before, and inputs that were rejected before are still rejected.

## Which issue does it fix?

Fixes #12

## How was it tested?

- Added `test_decimal_numbers` to `tests/test_size.py`, covering `"1.5k"` → 1536, `"0.5M"` → 524288 and `"2.25 KiB"` → 2304.
- Ran the full suite with `python3 -m unittest discover -s tests`: 8 tests, all passing.
- Checked edge cases by hand: `"2k"` → 2048, `"512"` → 512, `"1."` → 1, and `".5k"`, `"1.2.3k"` and `"lots"` still raise `ValueError`.

## AI assistance

Yes. Claude Code (Claude Haiku 5.5) was used to diagnose the bug, write the fix and its tests, and draft this description. I reviewed the diff and ran the tests myself.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
