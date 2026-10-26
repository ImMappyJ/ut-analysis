# Single-project, requirement-led UT analysis

This is the primary analysis workflow when the user supplies one project. The public Skill name
is `$ut-analysis`; no second project or comparison baseline is needed.
Use canonical mode `audit` with the analyzed project stored as internal ID A. A is an identifier,
not a requirement that the user phrase their request as "comparison project A".

## Inputs

Accept natural-language `项目 / project`, optional `分支 / branch`, `需求 / 产品目标`, `分析范围`,
optional module owners and explicitly supplied coverage/gate targets. Project may be a path or a
unique workspace project name. A clearly identified current repository may be used as the project;
do not guess one when the workspace contains several candidates.

Requirements can be the user's description, PRD/specification, acceptance criteria, user stories or
an explicitly supplied document directory. Use authorized local document readers for their formats;
if a format cannot be read, preserve the limitation rather than treating it as an empty requirement set.
Scope may be the whole project or named modules/files/requirements. Record the chosen scope and exclusions
in report_metadata.limitations and the actual project scan/coverage metadata.

```text
python <skill-root>/scripts/prepare_projects.py --project <project> --workspace <caller> --output <fresh-contexts.json>
```

One project selects audit automatically. `--branch` selects an isolated Git ref; omitted branch uses
the current working tree including local changes. Existing `--project-a` / `--branch-a` remain aliases.
The returned `analysis_root` is the only source root for scans/runs. Explicit external PRD paths can
stay outside that root, but record their provenance/version; never silently treat a different branch's
requirements as belonging to the selected commit.

## Analysis sequence

1. **Requirements before test conclusions.** Read explicit goals or clearly present requirement files.
   Build uniquely identified requirement units with their actual acceptance conditions, source excerpts
   and priority evidence. Record ambiguity, conflict and missing product evidence. This step precedes
   deciding what the existing UTs ought to verify; implementation is not an authoritative specification.
2. **Inventory and evidence.** Collect UT files, entry points/templates and native runtime instances;
   distinguish integration/E2E scope. Inspect implementation, test inputs, helpers, mocks and assertions.
   Identify the business outcome each assertion checks. Reconcile native collection and static discovery.
3. **Trace each requirement.** Map acceptance conditions to exact UT IDs and assertion locations.
   Use SUFFICIENT / PARTIAL / UNCOVERED / UNKNOWN. Requirements with no matching UT remain visible.
   UNCOVERED needs an adequately searched scope; unresolved collection or helper behavior can require
   UNKNOWN. UTs without a requirement association remain in the inventory and code-level review; do not
   invent requirements from names. Explain missing conditions and why assertions do/do not establish them.
4. **Execute and measure within scope.** Use existing execution/coverage adapters, fresh evidence and
   selected source context. Preserve PASS/FAIL/SKIP/ERROR/NOT RUN separately from requirement coverage.
   Collect line/branch/function metrics only when the native tool supplies them; preserve denominator,
   exclusions and pure-UT scope. Missing execution/coverage does not prevent an evidence-limited report.
5. **Review quality and prioritize next tests.** Distinguish confirmed product conflicts, inadequate
   assertions and suspected static findings. Check relevant normal/error/boundary/state/security conditions
   against actual requirements. Prioritize concrete gaps by business risk (P0/P1 or unclassified), with
   requirement ID, trigger/input, expected outcome, existing evidence, suggested test location and owner
   when supplied. Proposed test names are recommendations, never inventory entries or completed work.
6. **Render and support iteration.** Use schema 1.1.0, mode audit, projects=[A], matches=[] and no artificial
   B-only rows. Store source/criteria/traces/issues in quality and reproducible decisions in the normal
   quality evaluator. Existing output is docs/ut_result.html; caller evidence is docs/ut-diff/<run>/analysis.json
   for compatibility. Use examples/audit_input.json as the schema example, not a replacement for user data.

Read [requirement-traceability.md](requirement-traceability.md), [quality-rules.md](quality-rules.md) and
the relevant [framework-adapters.md](framework-adapters.md) sections. Reuse normal execution and
rendering scripts; Python validates/calculates, the Agent performs requirement interpretation and semantic review.

## Report and follow-up

Deliver a single-project report containing requirement coverage, UT inventory/results, quality findings,
measured coverage, gate reasons, and prioritized gap recommendations. No universal coverage threshold
is imposed. Without reliable requirements, product alignment is INSUFFICIENT EVIDENCE even if code-level
review is useful. High code coverage and all existing UTs passing cannot override a missing core scenario.

The [context query](context-query.md) reads requirement/UT/quality evidence directly from this report.
The [progress ledger](progress-tracking.md) can track later authorized repairs. Analysis alone does not
auto-edit business tests, change production behavior or mark proposals as completed. When the user
requests a repair, first check source freshness and then record real verification separately.

## Runnable synthetic acceptance example

```text
python <skill-root>/scripts/demo_e2e.py --mode audit --workspace <empty-demo-directory>
```

This scans and executes only the bundled Blue fixture, reads its explicit synthetic acceptance document,
and generates a one-project report. Existing tests pass, while one requirement is only partially checked
and one lacks a direct UT. This is fixed, reviewed demonstration data, not a generic semantic matcher.
`--no-execution` verifies the same pipeline with NOT RUN. The normal compare demo remains compatible.
