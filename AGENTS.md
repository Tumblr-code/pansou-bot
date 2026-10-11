# Repository workflow

- Use short-lived `codex/` branches and PRs. After review and successful required checks for the exact PR head, merge into `main` without asking again, then delete the merged remote branch. Never bypass branch protection or failed checks.
- `docs/SOURCE_MANIFEST.json` pins the runtime source (`main.py`, `requirements.txt`, `src/`). Regenerate it with `scripts/verify_source_manifest.py --update` in the same PR as any runtime change.
- Keep third-party attribution and existing license terms. Do not add a license to an unlicensed project on the owner's behalf.
- A GitHub release publishes files only; it does not deploy or restart anything.
- Keep both documentation languages aligned. Documentation is a public tutorial: no host names, addresses, account names or other details of anyone's own deployment.
- Never commit real environment files, tokens, user data, databases, caches or logs. Preserve unique unmerged branches and other tasks' worktrees.
