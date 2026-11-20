## What does this change?

`parse_size` dropped the fractional part of decimal sizes. The regex matched
the fraction but did not capture it, so `"1.5k"` was read as `1` kibibyte
and returned `1024` instead of `1536`. Whole numbers such as `"2k"` were
unaffected.

The fix captures the full number, multiplies it by the unit as a `Decimal`
so fractions stay exact, and then truncates to a whole number of bytes.
Results:

- `parse_size("1.5k")` → `1536` (was `1024`)
- `parse_size("1.5 MiB")` → `1572864`
- `parse_size("512")`, `parse_size("2k")` → unchanged

Only `tinyparse/size.py` changes in behaviour. `format_size` and
`parse_duration` are not touched.

## Which issue does it fix?

Fixes #12

## How was it tested?

Added `test_decimal_units` to `tests/test_size.py`, covering `"1.5k"`,
`"0.5k"`, `"1.5 MiB"` and `"2.25G"`.

- The new test fails on the previous code (`FAIL: test_decimal_units`) and
  passes with the fix.
- The full suite passes: `python3 -m unittest discover -s tests` (8 tests, OK).

## AI assistance

Yes. Claude Code (Claude Haiku 5.5) located the cause and drafted the change
and the test. The full suite was run locally before committing.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
