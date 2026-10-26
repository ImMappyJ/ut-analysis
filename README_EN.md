# UT-Analysis

[中文](README.md) · Skill **0.7.1** · Template **1.3.0** · Schema **1.1.0** · MIT

Analyze one project's unit tests against product requirements and acceptance criteria. Explain
assertion weaknesses, missing business scenarios and prioritized next tests. Two-project/branch Diff
is optional. The project is **UT-Analysis** and the invocation is `$ut-analysis`. The old `$ut-diff-report` installation is migrated; Python imports from `ut_diff_report` remain compatible.

```text
$ut-analysis
Project: ./my-project
Requirements: ./docs/acceptance.md
Scope: ordering module
Trace the existing UTs to acceptance criteria and prioritize assertion and scenario gaps.
```

One project automatically selects audit without asking for project B.
See [single-project analysis](references/single-project-analysis.md).

## Retrieve requirements, quality and repair context

Agents can read stored acceptance criteria, source excerpts, assertion evidence, quality findings,
coverage/gates and repair reasons directly from an existing report. Users need not copy page text.

```text
python scripts/query_context.py <workspace>/docs/ut_result.html --file test_inventory.py --project A
python scripts/query_context.py <workspace>/docs/ut_result.html --requirement REQ-INVALID --detail
python scripts/query_context.py <workspace>/docs/ut_result.html --section progress --progress <workspace>/docs/ut-progress
```

Queries default to paginated summaries and never execute tests or refresh historical conclusions.
See [context queries](references/context-query.md) for Python APIs, evidence boundaries and iteration usage.

The optional comparison workflow matches unit tests across two projects by business goal,
scenario, inputs, assertions and observed execution. Generates a standalone, offline HTML
report with aligned side-by-side Diff rows, unilateral blank placeholders, summary cards,
search, module/owner/status/priority filters, pagination and lazy disclosures.

Matching and execution are separate: two passing tests do not establish equivalent behavior.
Modes: **audit** (one project), **compare** (two projects), **full** (Diff plus quality).
Omitted mode selects audit for one project and compare for two; request full for combined quality analysis.
Product requirement/assertion traceability, measured coverage and configurable quality gates are separate
from semantic matching. Independent optional A/B branches use owned detached Worktrees; current dirty or
detached working trees are preserved. Same-repository branch comparisons are supported without switching
the user's checkout or silently fetching/falling back.
The accepted visual baseline is preserved, with its private data and narratives removed.
See the complete [synthetic HTML example](examples/sample_report.html), opened locally in a browser.
All static example results are explicitly NOT RUN; the runnable demo captures actual synthetic test results.
Additional complete examples: [audit](examples/audit_report.html), [full](examples/full_report.html).

![Synthetic report preview](docs/images/report-preview.jpg)

## Install on Windows

Requires Python **3.10+**, no Python runtime dependencies. This is distributed as a Skill/source
checkout, not a PyPI package. Go AST collection requires Go **1.18+**. Target tests need their own tools.

```powershell
git clone https://github.com/ImMappyJ/ut-analysis.git UT-Analysis
Set-Location UT-Analysis
python scripts/install_skill.py --mode link
```

## Install on Linux or macOS

```sh
git clone https://github.com/ImMappyJ/ut-analysis.git UT-Analysis
cd UT-Analysis
python3 scripts/install_skill.py --mode link
```

Replace the placeholder repository URL with the actual shared repository. No remote repository is
created by this project. Link mode uses a Windows junction or Unix symlink. Use `--mode copy` for an
independent installation. Default: CODEX_HOME/skills, or ~/.codex/skills when unset.
`--skills-dir <directory>` overrides it. Existing unrelated installations are never overwritten.
Source development and installation directories remain separate.
See [installation details](docs/installation.md), including safe copy updates and session refresh.

## Invoke in Codex

```text
$ut-analysis
Compare project A: ./project-blue
Compare project B: ./project-green
Optional module owners: Example Owner Alpha owns inventory; Example Owner Beta owns notifications.
Save docs/ut_result.html in the current workspace.
```

| Input | Required | Meaning |
| --- | --- | --- |
| Project (alias A) | Yes | Explicit absolute/relative path, unique workspace directory or manifest name |
| Project B | Only compare/full | A second project or another branch of the same repository |
| Module owners | No | Natural-language business-module mapping; multiple owners/modules supported |
| Destination | No | Caller workspace docs/ut_result.html by default |
| Regeneration authorization | If output exists | Explicit request required before --replace |
| Mode | No | One project → audit; two → compare; combined analysis → full |
| Analysis scope | No | Whole project or named modules/files/requirements; preserve exclusions and denominators |
| A/B branches | No | Independent refs; default current workspace; explicit refs use isolated Worktrees |
| Product goals | No | Natural language or PRD/spec/acceptance paths; implementation is not authoritative requirements |
| Coverage targets | No | Explicit approved percentages/core rules; no invented mandatory defaults |

The user does not author JSON/YAML. Codex reviews source, establishes goals and semantic decisions,
then writes canonical JSON internally. Python validates references/evidence and performs deterministic
statistics, line Diff and template rendering. Ambiguous projects require a candidate selection.

## Verify and try

```sh
python3 -m unittest discover -s tests -v
python3 scripts/validate_data.py examples/sample_input.json
python3 scripts/validate_report.py examples/sample_report.html
python3 scripts/demo_e2e.py --workspace .artifacts/demo
```

Use `python` on Windows. Demo workspace must be empty. The demo copies and executes only bundled
synthetic projects. Add `--without-owners --no-execution` with another new workspace to inspect honest
NOT RUN behavior. Actual execution timestamps are retained; unchanged canonical data renders identical bytes.

From a different workspace, try the static template with:

```text
python <skill-root>/scripts/render_report.py <skill-root>/examples/sample_input.json --workspace .
```

This renders sample data only. Full comparison is the Agent workflow, not an automatic Python semantic matcher.

## Scope and extension

Built-in collection: Python AST and Go AST. Runtime adapters: unittest, Go JSON and JUnit XML.
Other frameworks use native collection/reporters, source review and the same canonical schema.
Reconcile static inventory with native discovery; disclose dynamic/inherited/plugin/build-tag gaps.
Count top-level test entries/templates once; suites, parameter rows and runtime children are separate evidence.
No execution becomes NOT RUN, never a static PASS. Child equivalence needs explicit semantic keys.
Missing tests establish evidence gaps, not missing implementation. Measured code coverage is a separate task.

Owners attach to normalized business modules and do not imply completed review. Owner UI is hidden when
absent. P0/P1 priority needs a business-impact reason. Execution is not sandboxed; audit external effects
and dependencies first. No production/UT source rewrites, implicit dependency installation or publication.

See [usage and parameters](docs/usage.md), [architecture](docs/architecture.md),
[matching rules](references/matching-rules.md), [data schema](references/report-schema.md),
[framework adapters](references/framework-adapters.md), [template extension](references/template-extension.md),
[changelog](CHANGELOG.md) and [license](LICENSE).

Public fixtures/examples are synthetic. Keep real source/logs/owners/private data out of this repository.
CI is configured for Windows/Linux/macOS and Python 3.10/3.12; remote CI execution requires a future push.
Incremental semantic caches and automatic test migration are outside this release.

Single-project example:

```text
$ut-analysis
Mode: audit
Project A: ./project-blue
Product goals: ./requirements/acceptance.md
Coverage targets: 85% lines; all core requirements need sufficient assertion evidence.
```

For same-repository full analysis, specify A and B as the same directory and independent branches such as
main and feature/refactor. All collection/execution/coverage uses the prepared analysis_root. Preserve
artifacts before cleanup_worktrees.py; it only removes ownership-verified clean temporary trees.

Coverage readers: Go statement profiles (never relabeled lines/branches), coverage.py JSON, LCOV and
Cobertura counts. Use run_tests.py --fresh-output and calculate_coverage.py to bind artifacts to invocation
hashes/time/source context. Separate exporters require original test invocation and intermediate-data lineage.
Missing collection is not 0%. No trustworthy product evidence/configured policy means INSUFFICIENT EVIDENCE,
and high code coverage cannot cancel a failed core-requirement gate. Agent interprets goals; Python reproduces
the structured gate calculation. Quality PASS is not product release acceptance.
See [quality rules](references/quality-rules.md), [traceability](references/requirement-traceability.md),
[coverage collection](references/coverage-collection.md) and [Git contexts](references/git-analysis.md).

[Local verification and limitations](docs/verification.md)

## Retrieve a UT card from an existing report

Provide the report path and a UT name to `$ut-analysis`. The Agent calls `scripts/query_report.py`
or `ut_diff_report.card_query.get_ut_card`, returning the original aligned or audit-only card with its
assertions, execution evidence and relevant requirement traces. No source scan or tests run. Exact search
is default; repeated names produce candidates. New templates support automatic card-focus links; older
embedded-data reports remain readable without modification. See [query contract](references/card-query.md).

### All cards for a test file

Use `get_ut_cards(report_path, 'tests/test_inventory.py', project='A')` or
`python scripts/query_report.py report.html --file tests/test_inventory.py --project A`.
Returns every distinct matching card with its counterpart and evidence; no truncation.
Absolute file paths require --project-root. Omit project to search both sides.
See [the query contract](references/card-query.md).

## Incremental repair notes and summary-first queries

Version 0.5.0 prepares only changed Markdown task sections for Agent annotation and persists immutable snapshots. Unchanged notes need no repeated semantic analysis. CLI queries return summaries; --detail retrieves code and logs.

Template 1.3.0 collapses secondary statistics, filters and evidence, adds spacing and a separate repair-progress tab. Documentary progress never replaces historical results.

See [workflow](references/progress-tracking.md), [synthetic report](examples/progress_report.html), or run `python scripts/demo_progress.py --workspace <empty-directory>`.
