## What does this change?

`parse_size` ignored the fractional part of decimal amounts. The regex matched `1.5` but did not capture it, so `parse_size("1.5k")` returned 1024 instead of 1536. Whole numbers were not affected.

This change captures the full number, including the fraction, and multiplies it by the unit using `Decimal`, so the result is exact. The result is still an `int`; a fraction that does not land on a whole byte (for example `"1.3k"` → 1331.2 bytes) is rounded down.

## Which issue does it fix?

Fixes #12

## How was it tested?

- Added `test_decimal_amounts` to `tests/test_size.py`, covering `"1.5k"`, `"1.5M"` and `"0.5 GiB"`. It failed before the fix (`1024 != 1536`) and passes after.
- Ran the full suite: `python3 -m unittest discover -s tests` (8 tests, all pass).
- Checked by hand that whole numbers (`"512"`, `"2k"`, `"10k"`) are unchanged, and that malformed input (`".5k"`, `"1.2.3k"`, `"lots"`) is still rejected with `ValueError`.

## AI assistance

Yes. I used Claude Code to find the cause, write the test and make the change. I read and tested every line myself. The commit carries an `Assisted-by: Claude Code` trailer.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
