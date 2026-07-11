# Versioning

Version bumps are driven by [commitizen](https://commitizen-tools.github.io/commitizen/)
from the conventional-commit history. Config lives in
[pyproject.toml](../../pyproject.toml) under `[tool.commitizen]`
(`cz_conventional_commits`, `major_version_zero = true`, `update_changelog_on_bump = true`,
`tag_format = "v$version"`). The single source of truth for the current version is the
`version` field in `[project]`.

## Rule: bump the version before opening a PR

Right before opening a PR (before `gh pr create` / the `pr-push-and-merge` skill), bump the
version so every PR ships the version it warrants. Do NOT bump on every commit — cz collapses
all conventional commits since the last tag into one semver step, so one bump per PR is correct.

1. **Preview.** Run `uv run cz bump --dry-run`. It prints `bump: version X → Y` and the detected
   increment (`feat` → MINOR, `fix` → PATCH; under `major_version_zero` a breaking change is
   MINOR, staying in `0.x`).
2. **No increment → skip.** If the branch has only non-releasing commits since the last tag
   (`chore` / `docs` / `refactor` / `test` / `style` / `ci`), `--dry-run` reports no increment
   (or errors with no eligible commits). Open the PR without a bump — do not force one.
3. **Increment → bump files only.** Run `uv run cz bump --files-only --changelog --yes`. This
   updates `version` in [pyproject.toml](../../pyproject.toml) and writes `CHANGELOG.md`, but
   creates **no commit and no tag**. Then commit it on the branch, e.g.
   `git commit -am "chore(release): bump version to Y"`, so the version + changelog ride into the
   PR and survive the squash-merge.

**Never run a full `uv run cz bump` (commit + tag) on a PR branch.** PRs here squash-merge, so a
branch-local `vY` tag points at a commit that never lands on `main` — an orphaned tag that
corrupts the next "commits since last tag" calculation. (That mechanism is why a stray
`0.1.1` bump once stranded on an unmerged branch.)

## Tagging happens on `main`, after the merge

Once the PR squash-merges and `main` is re-pulled, create the release tag on the merge commit so
the next bump measures from the right base:

```bash
git tag "v$(uv run cz version --project)" && git push origin "v$(uv run cz version --project)"
```

Without this tag, cz keeps computing the increment from the previous tag and the version can
drift or double-count.
