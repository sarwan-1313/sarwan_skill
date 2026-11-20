## What does this change?

`parse_size` read the fractional part of a size and then discarded it, so `"1.5k"` returned 1024 instead of 1536. The number is now parsed as a `Decimal` and multiplied by the unit before converting to `int`, so fractional sizes keep their value. Whole numbers are unchanged.

## Which issue does it fix?

Fixes #12

## How was it tested?

- Added `test_decimals` to `tests/test_size.py`: `"1.5k"` gives 1536 and `"2.5 GiB"` gives 2.5 × 1024³.
- Ran `python3 -m unittest discover -s tests` on Python 3.13: 8 tests, all pass (7 before the change).
- Checked by hand that `"2k"`, `"10k"`, `"512"`, `"1.5M"` return 2048, 10240, 512 and 1572864.

## AI assistance

Claude Code helped write this change. I reviewed and ran every line myself.
