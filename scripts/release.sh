#!/usr/bin/env bash
set -euo pipefail

# Release script for ai-hedge-fund
# Usage: bash scripts/release.sh [version]
# If no version is provided, defaults to today's date as YYYY.M.D

VERSION="${1:-$(date +%Y.%-m.%-d)}"
TAG="v${VERSION}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$REPO_ROOT"

# Ensure gh CLI is available
if ! command -v gh &>/dev/null; then
  echo "Error: gh CLI is required. Install it: https://cli.github.com"
  exit 1
fi

# Ensure working tree is clean
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Error: working tree is dirty. Commit or stash changes first."
  exit 1
fi

# Find the previous tag (most recent), or use root commit if none exist
PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || true)
if [[ -z "$PREV_TAG" ]]; then
  RANGE="HEAD"
else
  RANGE="${PREV_TAG}..HEAD"
fi

echo "Releasing ${TAG}"
echo "Commits: ${RANGE}"
echo ""

# Collect commits and categorize into Changes and Fixes
CHANGES=""
FIXES=""

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  # Extract subject (everything after the short hash + space)
  subject="${line#* }"
  if echo "$subject" | grep -qi "^fix"; then
    FIXES="${FIXES}- ${subject}\n"
  else
    CHANGES="${CHANGES}- ${subject}\n"
  fi
done < <(git log --oneline --no-merges "$RANGE" | grep -v "^.*Bump version$")

# Build release body
BODY=""
if [[ -n "$CHANGES" ]]; then
  BODY+="### Changes\n\n${CHANGES}\n"
fi
if [[ -n "$FIXES" ]]; then
  BODY+="### Fixes\n\n${FIXES}\n"
fi

if [[ -z "$BODY" ]]; then
  echo "Error: no commits found for release notes."
  exit 1
fi

# Preview
echo "--- Release notes ---"
echo -e "$BODY"
echo "---------------------"
echo ""

# Prompt for confirmation
read -rp "Create release ${TAG}? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborted."
  exit 0
fi

# Bump version in pyproject.toml
CURRENT_VERSION=$(python3 -c "import re; print(re.search(r'^version\s*=\s*\"([^\"]+)\"', open('pyproject.toml').read(), re.M).group(1))")
if [[ "$CURRENT_VERSION" != "$VERSION" ]]; then
  python3 -c "
import re
with open('pyproject.toml', 'r') as f:
    content = f.read()
content = re.sub(r'^version\s*=\s*\"[^\"]+\"', 'version = \"${VERSION}\"', content, count=1, flags=re.M)
with open('pyproject.toml', 'w') as f:
    f.write(content)
"
  git add pyproject.toml
  git commit -m "Bump version to ${VERSION}"
  git push origin HEAD
fi

# Create tag
git tag "$TAG"

# Push tag
git push origin "$TAG"

# Create GitHub release
echo -e "$BODY" | gh release create "$TAG" \
  --title "ai-hedge-fund ${VERSION}" \
  --notes-file -

echo ""
echo "Released ${TAG}: https://github.com/virattt/ai-hedge-fund/releases/tag/${TAG}"
