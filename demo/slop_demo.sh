#!/bin/sh
# Builds a small project and a typical "slop" contribution to it, so you can watch sarwan_skill catch it.
#   sh demo/slop_demo.sh [folder]      (default folder: ./tinyparse-demo)
# Then:
#   cd tinyparse-demo && python3 ../skills/sarwan-skill/scripts/check.py all --pr pr.md
set -e
CHECK="$(cd "$(dirname "$0")/.." && pwd)/skills/sarwan-skill/scripts/check.py"
DIR="${1:-tinyparse-demo}"
rm -rf "$DIR" && mkdir -p "$DIR" && cd "$DIR"
git init -q && git symbolic-ref HEAD refs/heads/main
git config user.name "Demo" && git config user.email "demo@example.com" && git config core.autocrlf false
mkdir -p src tests
cat > CONTRIBUTING.md <<'EOF'
# Contributing to tinyparse

Sign off every commit (Signed-off-by, DCO).

## AI contributions

AI-assisted contributions are welcome, but you must disclose them with an
`Assisted-by:` trailer in your commit message. Please open an issue first
and wait for a maintainer to accept it before sending a pull request.
EOF
printf 'def parse(s):\n    return s.split(",")\n' > src/parse.py
printf 'def clean(s):\n    return s.strip()\n' > src/util.py
printf 'from src.parse import parse\n\n\ndef test_parse():\n    assert parse("a,b") == ["a", "b"]\n    assert parse("") == [""]\n' > tests/test_parse.py
printf '{"scripts": {"test": "pytest"}}\n' > package.json
printf '# lock\n' > yarn.lock
git add -A && git commit -qm "Initial version"
git checkout -qb fix-empty
# The slop: a debug print, a reformatted file, a skipped test, the agent's own files, the wrong lockfile...
printf 'def parse(s):\n    if not s:\n        return []\n    print("DEBUG", s)\n    return s.split(",")\n' > src/parse.py
printf 'def clean(s):\n    return s.strip()   \n\n\n' > src/util.py
printf 'import pytest\nfrom src.parse import parse\n\n\n@pytest.mark.skip\ndef test_parse():\n    assert parse("a,b") == ["a", "b"]\n' > tests/test_parse.py
printf '# my agent notes\n' > CLAUDE.md
printf 'step 1: fix parse\n' > PLAN.md
printf '{}\n' > package-lock.json
git add -A && git commit -qm "Fix empty input handling

Co-Authored-By: Claude <noreply@anthropic.com>"
cat > ../pr.md <<'EOF'
## 🚀 Summary
This PR introduces a comprehensive and robust fix that seamlessly improves parsing. ✨

## ✅ Changes
- Leverages best practices for empty input 🎉
EOF
echo "Demo ready in $DIR. Try:"
echo "  cd $DIR && python3 $CHECK all --pr ../pr.md"
