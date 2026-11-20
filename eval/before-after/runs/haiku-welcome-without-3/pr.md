## What does this change?

`parse_size` dropped the fractional part of decimal sizes. The regex matched `1.5k` but only captured the integer part (`1`), so the result was `1024` instead of `1536`. Whole numbers were unaffected.

The fix captures the full decimal number and multiplies it with `Decimal`, so the product is exact (no float rounding), then truncates to a whole number of bytes as before. Examples:

- `parse_size("1.5k")` → `1536` (was `1024`)
- `parse_size("0.5g")` → `536870912`
- `parse_size("1.9k")` → `1945` (truncated, same as the existing whole-byte behaviour)

Only `tinyparse/size.py` and `tests/test_size.py` change. `format_size` is untouched.

## Which issue does it fix?

Fixes #12

## How was it tested?

- Added `test_decimal_units` covering `1.5k`, `1.5M`, `0.5g` and `2.25 KiB`.
- The new test fails on the previous `size.py` (`FAILED (failures=1)`) and passes with this change.
- Full suite: `python3 -m unittest discover -s tests` → 8 tests, OK.

## AI assistance

Yes. Claude Code (Claude Haiku 5.5) helped locate the regex bug and draft the fix and test. The change was checked against the test suite locally (see above). The commit carries an `Assisted-by: Claude Code` trailer.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
