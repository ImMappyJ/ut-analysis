# Template maintenance

Skill 0.5.0; schema 1.1.0 (compare 1.0.0 compatible); template 1.3.0.

report.css is the normalized UTF-8 stylesheet extracted from the approved baseline, unchanged.
Its SHA256 is recorded in assets/provenance.json. It retains layout, typography, palette, cards,
two-pane alignment, responsive, dark and print rules. HTML retains the static skeleton with placeholders.
JS retains row/Diff/search/pagination/lazy disclosure; private narratives are removed, project metadata
is generic, optional owner controls added and child association uses explicit semantic scenario keys.
The user authorized sanitized reuse and MIT licensing. No original business records/logs are distributed.

Extension steps:

1. Define canonical fields/schema before rendering them. Keep semantic inference in the Agent.
2. Update deterministic view_data conversion, never invent business goals or matches in Python.
3. Use DOM textContent, never innerHTML for source/logs. Escape JSON `<`, `>`, `&`, U+2028/U+2029.
4. Keep CSP/offline assets; add tests and regenerate synthetic example; check browser interactions.
5. Increment template version in package/provenance, Skill SemVer and CHANGELOG. Breaking contracts need schema version change.

Template markers REPORT_TITLE, REPORT_CSS, UT_DATA and REPORT_JS, each enclosed by two underscores,
must appear once. A single substitution pass prevents inserted user text becoming another template instruction.
No CDN/runtime service. Public examples must remain synthetic and clearly disclose NOT RUN.

1.1.0 adds quality.css/quality.js only in audit/full. Compare keeps its original stylesheet and controls.
Audit hides the comparison container, without a fake B; full switches between the retained Diff and
independent requirement/coverage/issues/gates panels. Requirement and UT details are lazy and searchable.
Git branch/SHA/dirty labels are metadata, not a change to matching/layout rules.

1.3.0 adds progress.css/progress.js: user-requested less crowded layout, collapsed secondary
statistics/filters and evidence sections, 40-row default pages, separate documentary progress view.
The original report.css hash remains unchanged; overrides share its palette and responsive rules.
view_html renders archived inventory into the current template without recomputing historical data.
Progress is a separate optional embedded field; baseline_report_sha256 and meta.presentation keep
original execution time/version distinct from the presentation update.
