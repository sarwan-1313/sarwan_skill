## What does this change?

`parse_size` dropped the fractional part of decimal sizes. The regex matched `1.5` in `"1.5k"` but only the integer digits were used, so `parse_size("1.5k")` returned `1024` instead of `1536`.

This change:

- Parses the full decimal number with `decimal.Decimal`, so `"1.5k"` gives `1536`, `"1.5M"` gives `1572864`, and so on. `Decimal` avoids float rounding.
- Raises `ValueError` when the result is not a whole number of bytes (for example `"1.5"`), instead of silently truncating it.

Whole-number inputs such as `"512"`, `"2k"` and `"1 GiB"` behave as before.

## Which issue does it fix?

Fixes #12

## How was it tested?

- Added `test_decimal_units` (`1.5k`, `1.5M`, `2.25g`) and `test_rejects_fractional_bytes` (`1.5`) to `tests/test_size.py`.
- The two new tests fail on the previous `tinyparse/size.py` and pass with this change.
- Full suite: `python3 -m unittest discover -s tests` runs 9 tests, all passing.

## AI assistance

Yes. Claude (Claude Code, model Haiku 5.5) wrote the code change, the tests and this description.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
