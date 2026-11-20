## What does this change?

`parse_size` dropped the fractional part of a number, so `"1.5k"` returned 1024 instead of 1536. The regex now captures the whole number, and the value is converted with `float` before applying the unit. The change is in `tinyparse/size.py`, plus a regression test in `tests/test_size.py`.

## Which issue does it fix?

Fixes #12

## How was it tested?

- `python3 -m unittest discover -s tests`: 8 tests, all pass.
- New `test_decimal_units` fails on the old code (`1024 != 1536`) and passes with the fix.
- Spot checks: `"1.5k"` → 1536, `"1.5M"` → 1572864, `"1.1k"` → 1126, `"2k"` → 2048, `"512"` → 512, `"lots"` still raises `ValueError`.

## AI assistance

I used Claude Code to help write this change. I read and tested every line, and the commit carries an `Assisted-by: Claude Code` trailer.
