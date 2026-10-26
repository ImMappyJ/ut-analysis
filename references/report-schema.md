# Canonical data 1.1.0

The Agent prepares internal JSON; users supply natural-language projects and optional owners.
[report.schema.json](report.schema.json) is the machine-readable Draft 2020-12 schema;
[sample_input.json](../examples/sample_input.json) is a complete synthetic example.
The stdlib validator supports exactly the schema's used keywords: $ref, type, enum, const,
properties, required, additionalProperties, items, minItems, minLength, pattern, minimum.
It also checks references, unique accounting and runtime provenance. It is not a general JSON Schema engine.

| Field | Meaning |
| --- | --- |
| schema_version | 1.1.0; legacy 1.0.0 remains accepted for compare only |
| report_metadata | explicit mode=compare/audit/full, title/run ID/time, counting policy, limitations, findings; legacy data without mode remains compare |
| projects | A+B in compare/full; A only in audit. Names, roots/revisions, actual Git context, frameworks, scan scope/errors |
| modules | Business IDs/names, mapping evidence, optional priority/reason and owner IDs |
| owners | Optional IDs/names; absent/empty hides owner UI |
| test_cases | Entries including excluded kinds: stable ID, project-relative path, source line/code, goal/evidence |
| matches | Every UT in one main row in compare/full; empty in audit, without a fictional B |
| execution_results | One selected observation per entry, provenance, children and optional history |
| differences | Source-backed scenario/input/assertion/code/execution/coverage notes for matches |
| summary | Optional; if supplied must equal the complete computed summary |
| quality | Required in audit/full; validated against quality.schema.json and evaluated independently |

Use stable_id(project_id, path, qualified_locator) from discovery.py or another stable source identity.
No random IDs; source line alone is insufficient. Paths cannot be absolute or escape via '..'.
In compare/full each unit entry occurs once in matches; audit has no matches. Excluded kinds never occur there. Related references do not count.
Two-sided entries use normalized module IDs.

Every goal describes trigger/inputs/expected behavior; evidence points to source and assertions.
Nonempty evidence is validated, its truth still requires Agent source review.
Assertions: `{code,line,method?}`; subtests: `{name,expression?,line,code}`;
parameter_tables: `{line,rows:[{name,line,code}]}`; helpers/globals: `{name,path,line,code}`.
Static candidates do not imply actual execution instances.

Executed results require command argv, ISO run_at, environment and evidence references. Keep elapsed seconds,
stdout/stderr, exit code and fingerprint when available. NOT RUN requires reason; omitted results become
NOT RUN with missing-evidence reason. Children: `{name,status,scenario_key?,elapsed_seconds?,output?}`.
Child semantic keys must be explicitly verified and unique per parent, never inferred from names by Python.
`cached:true` retains historical time; history preserves earlier invocation evidence.

Identical inputs/assets render identical bytes. Embedded `script#ut-data` is an internal view model,
not a second authoring contract. Python computes statistics and code Diff, not goals or semantic matches.

## Quality evidence

quality.schema.json defines sources, normalized requirements/criteria, per-project traces, quality issues,
actual coverage records, explicitly reviewed UT IDs and user/standard-based policy. Complete synthetic
examples: audit_input.json (no invented product goals), full_input.json (shared requirements, partial coverage).
Requirements keep unique IDs, source excerpts, priority and testability. Each trace retains actual UT IDs,
criterion IDs and assertion path/line/code/validity. SUFFICIENT needs every acceptance condition supported.
Coverage uses actual integer covered/total counts with tool/version, command/time, UT scope, artifact hash,
denominator/exclusions, unmeasured files and selected source context. Uncollected records have a reason and
no metric percentages. File/global counts must agree when file details exist.
Policy has independent code/requirements/effectiveness gates; no implicit percentage threshold.
See quality-rules.md, requirement-traceability.md and coverage-collection.md for evidence and judgment rules.

## Git evidence

projects[].git is the selected context from prepare_projects.py: current/default working tree or an owned
isolated explicit branch snapshot. Preserve actual SHA, branch/detached label, dirty state, roots and fingerprint.
For an observed result or collected coverage with selected SHA, source_context must match that SHA and
analysis_root and include a real fingerprint. A dirty working-tree observation is not a pristine commit result.
Branch metadata never determines UT semantic matches. See git-analysis.md for resolution and cleanup.
