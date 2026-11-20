## What does this change?

`parse_size` dropped the fractional part of the number before applying the unit, so `"1.5k"` returned `1024` instead of `1536`. The regex now captures the whole number, and the multiplication uses `Decimal` so it stays exact. The result is still truncated to whole bytes.

Whole numbers behave as before (`"2k"` is still `2048`).

## Which issue does it fix?

Fixes #12

## How was it tested?

- Added `test_decimal_units` to `tests/test_size.py` covering `1.5k`, `1.5M` and `0.5g`. It failed before the fix (`1024 != 1536`) and passes after.
- Ran `python3 -m unittest discover -s tests`: 8 tests, all pass.
- Spot-checked `parse_size` by hand for `2k`, `512`, `1 GiB`, `1.25 KiB`, and invalid inputs such as `lots` and `1..5k`. Those still raise `ValueError`.

## AI assistance

Claude Haiku 5.5 (via Claude Code) helped locate the bug and write the change and test. I reviewed every line and ran the test suite myself.
