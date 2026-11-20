## What does this change?

`parse_size` now keeps the fractional part of the number. The regex matched the decimals but did not capture them, so `"1.5k"` was read as `1k`. The number is now parsed with `Decimal` and truncated to an int after scaling. I added a test for decimal inputs.

## Which issue does it fix?

Fixes #12

## How was it tested?

Ran `python3 -m unittest discover -s tests`: 8 tests, all OK, including the new `test_decimals` (`"1.5k"` gives 1536). I did not run any other checks.

## AI assistance

I used Claude Code to help write this fix and test. I reviewed and ran every change. The commit has an `Assisted-by: Claude Code` trailer.
