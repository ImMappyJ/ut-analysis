# Changelog

## 0.7.1 — 2026-10-26

- Renamed project and display name to UT-Analysis; Skill command and install folder are ut-analysis.
- Preserved the Python package ut_diff_report, report paths and historical evidence formats.
- Migrated the local source checkout and installation junction without discarding files.

## 0.7.0 — 2026-10-26

- Made requirement-led, single-project UT analysis a primary workflow; UI name is UT-Analysis.
- Preserved the existing installation, Python package, schema and report template compatibility.
- Project preparation auto-selects audit for one project and compare for two, with neutral --project/--branch aliases.
- Added requirement-first guidance and an actual single-project synthetic execution demo with explicit acceptance criteria and missing scenarios.
- Explicit compare/full without project B still fails; existing Diff/query/progress workflows remain available.

## 0.6.0 — 2026-10-23

- Added read-only report context APIs and query_context.py for requirements, quality and repair progress.
- Exact UT/file/requirement/issue/progress selectors, project/module filters and explicit pagination.
- Summary-first responses with on-demand source excerpts, acceptance criteria and assertion evidence.
- Preserved old card APIs, template 1.3.0, historical judgments and live-versus-embedded progress freshness.

## 0.5.0 — 2026-10-22

- Hash-based incremental Markdown task preparation, Agent annotations and immutable progress snapshots.
- Source-quoted documentary progress, stale/removed source warnings and exact baseline binding.
- Summary-first CLI and get_ut_context; full Python card APIs remain backward compatible.
- Template 1.3.0: collapsed secondary statistics/filters/evidence, more spacing, 40-row Diff pages,
  separate repair-progress tab with search, filters, pagination and card navigation.
- Notes synchronization preserves historical matching/results and never claims fresh test execution.

## 0.4.0 — 2026-10-22

- Read-only get_ut_cards API and query_report.py --file return all cards for an exact test file.
- Optional A/B scoping, shared-row deduplication, complete counterpart/quality evidence and no truncation.
- Portable lexical absolute-path conversion with explicit project root; original name/ID queries retained.
- Template remains 1.2.0; repair-progress integration remains a separate design proposal.

## 0.3.0 — 2026-10-21

- Read-only get_ut_card API and query_report.py CLI for existing report + UT name/ID lookups.
- Exact/explicit contains search, project/path disambiguation and same-row deduplication.
- Archived runtime-instance and relevant product trace/issue evidence retained with report SHA/time.
- Template 1.2.0 card deep links expand the correct paginated Diff row or audit inventory entry.
- Older embedded-data reports remain queryable without rewriting or executing them.

## 0.2.0 — 2026-10-21

- compare / single-project audit / full modes with backward-compatible compare data.
- Shared product requirement IDs, assertion traceability and explicit evidence insufficiency.
- Actual Go/coverage.py/LCOV/Cobertura artifact normalization and configurable three-layer quality gates.
- Independent quality views; retained baseline stylesheet and original two-pane interactions.
- Independent A/B Git branch resolution and owned detached Worktrees; current dirty/detached state preserved.
- Native run/artifact hashes and selected-source context verification; guarded owned-resource cleanup.
- Canonical schema 1.1.0 and template 1.1.0; synthetic audit/full examples and regression tests.

## 0.1.0 — 2026-10-21

- Independent installable MIT Skill; Python standard library runtime.
- Approved and sanitized visual template 1.0.0; canonical schema 1.0.0.
- Agent semantic workflow; deterministic evidence validation, statistics and atomic offline output.
- Normalized modules, P0/P1 and optional owner filters/statistics.
- Python/Go AST; unittest/Go JSON/JUnit evidence adapters.
- Synthetic examples, portable installation, automated tests and cross-platform CI.
