#!/usr/bin/env bash
#
# Rewrite all commit author / committer fields in this repo to drop the
# personal Gmail and use the Vurctne brand identity instead.
#
# Why: the local history (2 commits as of 2026-04-26) was authored by
# `wang.zili.ivan@gmail.com` (personal Gmail). Before pushing publicly,
# we want history to read as `Vurctne <contact@vurctne.com>`.
#
# When to run: ONCE, before pushing publicly. Safe because no remote is
# configured yet — no force-push divergence to worry about.
#
# What this changes:
#   - Author and committer email/name on EVERY commit
#   - Commit hashes (history is rewritten, so SHAs all change)
#
# What this does NOT change:
#   - File contents, commit messages, commit timestamps
#
# Pre-flight:
#   - Working tree must be clean. If `git status` shows modifications,
#     either commit them first or `git stash --include-untracked`.
#   - No remote configured.
#
# Verify after: `git log --format='%h %ae %an %s'` should show only the
# Vurctne identity.
#
# ─── Run from this directory ─────────────────────────────────────────────

set -euo pipefail

cd "$(dirname "$0")"

OLD_EMAIL="wang.zili.ivan@gmail.com"
NEW_NAME="Vurctne"
NEW_EMAIL="contact@vurctne.com"

if ! git log --format='%ae' 2>/dev/null | grep -qi "$OLD_EMAIL"; then
  echo "ERROR: did not find any commits by $OLD_EMAIL — not safe to run."
  echo "Verify you're in the Vic_School_Finance_Tools repo and try again."
  exit 1
fi

if git remote get-url origin >/dev/null 2>&1; then
  echo "ERROR: a remote is already configured."
  echo "If history has already been pushed, rewriting will require"
  echo "force-push and will break anyone who pulled it. Aborting."
  exit 1
fi

echo "Rewriting all commits authored by $OLD_EMAIL"
echo "  →  $NEW_NAME <$NEW_EMAIL>"
echo

export FILTER_BRANCH_SQUELCH_WARNING=1

git filter-branch --env-filter "
  if [ \"\$GIT_AUTHOR_EMAIL\" = '$OLD_EMAIL' ]; then
    export GIT_AUTHOR_NAME='$NEW_NAME'
    export GIT_AUTHOR_EMAIL='$NEW_EMAIL'
  fi
  if [ \"\$GIT_COMMITTER_EMAIL\" = '$OLD_EMAIL' ]; then
    export GIT_COMMITTER_NAME='$NEW_NAME'
    export GIT_COMMITTER_EMAIL='$NEW_EMAIL'
  fi
" --tag-name-filter cat -- --all

echo
echo "Done. Verify with:"
echo "    git log --format='%h %ae %an %s'"
