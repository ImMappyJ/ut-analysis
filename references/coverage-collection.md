# Actual coverage collection

Inspect installed language/framework tools before running. Examples: native Go coverprofile; installed
coverage.py/pytest-cov; JavaScript LCOV; JVM/.NET Cobertura exports. Do not silently install dependencies.
Select known UT entries after inventory; default framework suites may also contain integration/E2E tests.
Run UT-only commands or label scope MIXED/UNKNOWN. Native package setup may have external effects: audit first.

Record command, UTC time, selected analysis root/SHA/working state, test scope evidence, tool/version,
actual executable denominator, exclusions and unmeasured files/modules. Missing metrics are uncollected.
No AI estimation, source-line counting proxy or test-count-based percentage.

```text
python <skill-root>/scripts/run_tests.py --project <selected-analysis-root> --artifacts <fresh-run-dir> --framework go --fresh-output <fresh-coverprofile> -- go test -json -count=1 -coverprofile=<fresh-coverprofile> <audited-UT-selection>
python <skill-root>/scripts/calculate_coverage.py --input <coverprofile> --format go --invocation <fresh-run-dir>/invocation.json --project-id A --tool "go test" --tool-version <observed-version> --scope UT --scope-evidence <actual-UT-selection-reason> --strip-prefix <actual-module-prefix> --output <fresh-normalized.json>
```

The recorder refuses existing declared output artifacts and records their hashes. The normalizer verifies
the artifact hash against that invocation, rejects stale/incomplete/failed collection and source changes,
and preserves provenance. It does not determine UT scope semantically: Agent must justify the selected tests.

Formats:

- go: measured block statement coverage; not line or branch coverage. Uncovered blocks retain line ranges.
- coveragepy: coverage.py JSON executable lines and reported branch exits; no inferred function counts.
- lcov: DA/BRDA/FNDA or native LF/LH/BRF/BRH/FNF/FNH counts; reject inconsistent detailed/summary counts.
- cobertura: executable line hits and detailed condition-coverage counts; aggregate-only exports cannot
  establish per-module coverage. No root percentage reverse-calculation.

Module attribution uses explicit normalized module `project_scopes` path patterns. Missing scope mapping is
missing module evidence, not 0%. Overlapping module views are not summed to obtain the global denominator.
Global counts derive once from actual reported files. `--exclude` records actual native exclusions; it does
not silently change a parsed denominator. `--strip-prefix` normalizes declared measured source paths only.

For tools that separate test execution and export (coverage.py), retain both invocations and bind the
intermediate data artifact to the original test run. A newly exported JSON from old coverage data is not
fresh coverage. See calculate_coverage.py --help for the explicit lineage arguments as supported.
If the tool is unavailable or the evidence chain cannot be established, record collected:false and reason.
Optional condition/mutation metrics also need actual tool counts and authorization; no synthetic estimates.

For a two-step collector, declare the fresh intermediate file in the original test capture and the fresh
report in the export capture. The export argv must explicitly select that intermediate file (absolute or
relative to its recorded cwd). Normalize with:

```text
python <skill-root>/scripts/calculate_coverage.py --input <fresh-export.json> --format coveragepy --invocation <export-run>/invocation.json --test-invocation <test-run>/invocation.json --data-artifact <fresh-original-data> --project-id A --tool coverage.py --tool-version <observed-version> --scope UT --scope-evidence <audited-selection> --output <fresh-normalized.json>
```

Both successful invocations must use an unchanged, identical source fingerprint. The intermediate and final
artifacts must match their producer hashes. This prevents relabeling a fresh export of stale data as a fresh
UT execution. `run_tests.py --framework unittest --test-id module.Class.test_method` can select explicit
reviewed unittest IDs instead of a discovery pattern; repeat --test-id for several entries.
