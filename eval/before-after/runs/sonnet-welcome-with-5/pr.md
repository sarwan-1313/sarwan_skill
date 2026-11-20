## What does this change?

`parse_size` matched the decimal part of a number but discarded it, so "1.5k" gave 1024. The whole number, including the fraction, is now multiplied by the unit (using `Decimal` to avoid float error and still return an `int`). Adds a test for decimal inputs.

## Which issue does it fix?

Fixes #12

## How was it tested?

Reproduced `parse_size("1.5k") == 1024` before the change. After it, `python3 -m unittest discover -s tests` passes (8 tests), including the new `test_decimals`.

## AI assistance

I used Claude Code to write the fix and test. I reviewed and ran every change. The commit has an `Assisted-by: Claude Code` trailer.
