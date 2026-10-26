# Git branches and isolated source contexts

Project preparation defaults to auto: one project selects audit, two select compare. Explicit full
includes quality analysis and requires two projects. `--project`/`--branch` are neutral aliases for
`--project-a`/`--branch-a`. Explicit compare/full without B fails; it never silently changes the task.

```text
python <skill-root>/scripts/prepare_projects.py --project <repo> --workspace <workspace> --output docs/ut-diff/<run>/contexts.json
```

All modes accept independent optional A/B branch selections. No branch selection means current working
code, including dirty files, without checkout. Detached HEAD uses its actual commit and label. An unborn
repository has no commit SHA; a non-Git project remains usable unless a branch was explicitly requested.

```text
python <skill-root>/scripts/prepare_projects.py --mode full --workspace <workspace> --project-a <repo> --branch-a main --project-b <repo> --branch-b feature/refactor --output docs/ut-diff/<run>/contexts.json
```

Audit takes A only; omit project-b/branch-b. Specifying only branch-a or only branch-b is supported.
Read the manifest and use each `analysis_root` for all later scanning, test and coverage commands.
Copy the corresponding context to canonical `projects[].git`. Do not continue to scan the original
directory after an explicit branch selection.

Resolution: exact local branch first; then exact existing remote-tracking ref or a unique remote leaf.
Ambiguous remote leaves require selection. Missing branches stop that side; no fallback and no auto-fetch.
Remote tracking refs are cached local observations, not a claim of the latest remote state.

Explicit selection creates a detached Worktree at a fresh OS temporary location, outside the user's
source tree. A subproject path is retained relative to the selected repository. Hooks are disabled for
this checkout command only; no repository/global config changes. No new branch, merge, history rewrite,
push or submodule initialization. If submodules/dependencies are unavailable, disclose execution gaps.

Record actual selected branch/ref, full commit, original repository, analysis directory, dirty state,
snapshot fingerprint, test time and command. Current-working-tree results are working-tree observations,
not proof of a pristine commit. Explicit branch snapshots exclude original uncommitted changes;
`source_has_uncommitted_changes` records those original changes separately.
Runtime capture records actual SHA/root/fingerprint. Canonical results and coverage with Git metadata
must match the selected SHA, analysis root and source fingerprint; metadata alone cannot prove which source a command used.

```text
python <skill-root>/scripts/cleanup_worktrees.py <workspace>/docs/ut-diff/<run>/contexts.json
```

Cleanup checks its random ownership marker, exact temporary path, registered Worktree and original SHA.
It only removes the clean Worktree created by this task, with ordinary `git worktree remove`, never force.
If changed/dirty it is retained for inspection. Original/user Worktrees are not cleanup candidates.
Preserve scan/code/runtime/coverage evidence before removal because the temporary source path then disappears.
Cleanup errors must be reported, not hidden. Partial checkout failures name their retained owned directory.

## Source fingerprint scope

The analysis fingerprint binds Commit SHA (or unborn HEAD) to input bytes under the actual project root,
including source, configuration and test data. Symlink targets are hashed without following them. It excludes
Git metadata, vendor/node_modules/virtualenv/cache directories, `.artifacts`, `.local`, `.coverage*`, `htmlcov`,
and this workflow's `docs/ut-diff/**` and `docs/ut_result.html` outputs. See execution.source_digest for the
exact list. Keep any other generated evidence outside the selected source tree. Source mutation during a run
invalidates stable coverage collection. A separate repository_snapshot_digest records the broader tracked /
non-ignored working-tree snapshot; it is not used to mistake newly written report evidence for source changes.
Runtime details retain the observation at execution time, including dirty state. Initial preparation metadata
is not a substitute for actual run evidence or a proof that the entire repository was pristine.
