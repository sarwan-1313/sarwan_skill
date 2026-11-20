## What does this change?

`parse_size` ignored the fractional part of a number. The regex matched the integer digits and discarded the decimal part, so `parse_size("1.5k")` returned `1024` instead of `1536`. Whole numbers were unaffected.

The fix captures the full decimal number and multiplies it with `Decimal` before truncating to an `int`, so the result is exact (`1.5k` → `1536`, `2.5M` → `2621440`, `0.5 GiB` → `536870912`).

Behavior for inputs that yield a fractional byte count (e.g. `"0.3k"` = 307.2 bytes) is unchanged in spirit: the result is truncated toward zero, as `int()` already did for whole-number inputs. No other behavior changes.

## Which issue does it fix?

Fixes #12

## How was it tested?

- Added `test_decimal_values` to `tests/test_size.py` covering `1.5k`, `2.5M` and `0.5 GiB`. It fails on `main` and passes with this change.
- Full suite: `python3 -m unittest discover -s tests` → 8 tests, OK.

## AI assistance

Claude Haiku 5.5 (via Claude Code) helped locate the bug and draft the fix and test. I reviewed the change and ran the test suite myself.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
