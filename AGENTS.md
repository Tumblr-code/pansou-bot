# Repository workflow

- Use short-lived `codex/` branches and PRs. After review and successful required checks for the exact PR head, merge into `main` without asking again, then delete the merged remote branch. Never bypass branch protection or failed checks.
- The image bundles the PanSou engine at the upstream revision in `engine/UPSTREAM`; `engine/build.sh` is the only way it is compiled (Dockerfile and the Engine release workflow both call it). Do not vendor or patch upstream engine code here; bump the pin with `scripts/bump_engine.sh` in a PR.
- Engine releases (`engine-<YYYYMMDD>-<rev12>`, assets `pansou-linux-<arch>.tar.gz` + `SHA256SUMS`) are a contract with `src/engine_updater.py`: change both together.
- Keep third-party attribution and existing license terms; the bundled engine's MIT LICENSE must ship with every image and archive. Do not add a license to this unlicensed project on the owner's behalf.
- A GitHub release or image publish does not deploy or restart anything.
- Keep both documentation languages aligned. Documentation is a public tutorial: no host names, addresses, account names or other details of anyone's own deployment.
- Never commit real environment files, tokens, user data, databases, caches or logs. Preserve unique unmerged branches and other tasks' worktrees.
