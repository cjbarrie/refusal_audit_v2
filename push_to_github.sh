#!/usr/bin/env bash
# One-time: initialize this repo, verify no secrets are staged, create a PRIVATE
# GitHub repo named "refusal_audit_v2" under your account, and push.
#
# Run from the repo root:  bash push_to_github.sh
#
# Requires the GitHub CLI (gh). If you don't have it:  brew install gh  &&  gh auth login
set -euo pipefail

cd "$(dirname "$0")"

# --- identity (matches your other nyu_projects repos) ---
git init
git config user.name  "cjbarrie"
git config user.email "chrisjbarrie@googlemail.com"
git branch -M main

# --- stage everything (.gitignore already excludes .env, __pycache__, .DS_Store, LaTeX cruft) ---
git add -A

# --- SAFETY GATE: refuse to continue if .env or any secret-looking file is staged ---
if git diff --cached --name-only | grep -qiE '(^|/)\.env$|secret|token|credential|\.pem$|\.key$'; then
  echo "ABORT: a secret-looking file is staged. Inspect 'git diff --cached --name-only' before proceeding."
  exit 1
fi
echo "Secret check passed — .env is not staged."

git commit -m "Initial commit: refusal_audit v2 pipeline (sourcing, generation, annotation, R analysis, writeup)"

# --- create the private repo and push (gh reads your authenticated account) ---
gh repo create refusal_audit_v2 --private --source=. --remote=origin --push

echo "Done. Repo pushed to: https://github.com/cjbarrie/refusal_audit_v2 (private)"
