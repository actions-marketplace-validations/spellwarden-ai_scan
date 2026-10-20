#!/usr/bin/env bash
# Spec 9.5: the base-settings case reads its settings file from the pull request's base commit, so the base must
# already hold the case. The pull request that adds it (a release branch into main) cannot pass it; this guard
# skips the case there, with a notice, and runs it on every later pull request.
# Usage: BASE_SHA=<base commit> GH_TOKEN=<job token> GITHUB_API_URL=... GITHUB_REPOSITORY=... GITHUB_OUTPUT=<file> \
#   bash .github/scripts/base_has_case.sh <file of the case>
# It asks the contents API and never touches the checkout: the base commit must stay out of the clone, so that the
# scanner's own one-commit fetch through the persisted credentials is what the case exercises. Writes
# present=true|false to $GITHUB_OUTPUT; any answer but 404 (an error, no answer) is present=true, so the case runs
# and fails loudly instead of being skipped.
set -euo pipefail
case_file="$1"
status="$(curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "$GITHUB_API_URL/repos/$GITHUB_REPOSITORY/contents/$case_file?ref=$BASE_SHA")" || status="none"
if [ "$status" = "404" ]; then
  echo "present=false" >> "$GITHUB_OUTPUT"
  echo "::notice::base-settings skipped: the base commit does not hold $case_file yet (this pull request adds the case); it runs on the next pull request."
else
  echo "present=true" >> "$GITHUB_OUTPUT"
fi
