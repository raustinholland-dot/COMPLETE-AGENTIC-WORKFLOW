# /commit — Commit all pending changes to git

Stage and commit all modified and new files in the project (excluding secrets and ignored files), with an auto-generated commit message summarizing what changed.

## What to do

1. Run `git status --short` to see what's changed
2. Stage all relevant files (never stage `.env`, `*.secret`, or anything in `.gitignore`)
3. Write a concise commit message based on what actually changed
4. Run `git commit` with that message
5. Confirm success and show the commit hash

## Rules
- Never stage `.env` or any file containing secrets
- Never push — just commit locally unless Austin explicitly says to push
- Always use a descriptive commit message (not just "update")
- If nothing to commit, say so clearly
