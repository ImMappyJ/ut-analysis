# Report context queries

Extend the existing read-only report reader with a summary-first query for requirements,
quality findings/coverage/gates, and repair progress. Agent callers should obtain stored acceptance
criteria and source excerpts themselves rather than asking users to copy text from the page.

Add `get_report_context` plus `get_requirements`, `get_quality`, and `get_repair_progress` wrappers
and a standalone `query_context.py` CLI. Keep existing card APIs and HTML presentation unchanged.
Support exact requirement/issue/progress IDs, UT identity or file, project and stable module ID.
Return per-collection pagination, explicit absence and ambiguity, report provenance, and documentary
progress freshness. Project quality conclusions remain labelled project-wide even when querying a file.
Never infer requirement links by keywords, refresh historical judgments, follow evidence references,
execute report scripts/tests, or mutate the report during lookup.

Implementation: add regression tests; implement reader and CLI; document routing and examples;
run full regression, a separate workspace CLI smoke test and installed-path checks. Existing private
report is used only for read-only smoke checks; public examples remain synthetic.
