## What does this change?

`parse_size` dropped the fractional part of a size, so `parse_size("1.5k")` returned `1024` instead of `1536`. The regex matched the decimal part but did not capture it. The number is now captured in full and scaled with `Decimal`, so the result is exact.

A value that does not come out to a whole number of bytes (for example `"1.0001k"` or `"1.5"`) now raises `ValueError`. Previously it was silently truncated. This is a small behaviour change; say if you would rather truncate.

## Which issue does it fix?

Fixes #12

## How was it tested?

- Added `test_decimal_units` (`1.5k`, `0.5k`, `1.5M`, `2.5 GiB`) and `test_rejects_fractional_bytes` (`1.5`) to `tests/test_size.py`.
- Before the change, `parse_size("1.5k")` returned `1024`, so the new test reproduces the bug.
- Full suite passes: `python3 -m unittest discover -s tests` (9 tests, Python 3.13).

## AI assistance

Yes. Claude (Claude Haiku 5.5, via Claude Code) wrote the code change, the tests and this description. The contributor reviewed the change before submitting.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
