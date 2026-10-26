# Single-project requirement analysis as a primary workflow

The quality engine and report schema already support audit. The main gap is entry routing:
CLI project preparation defaults to compare, the Skill asks for A/B, and the runnable demo is dual-project.

Keep the source folder, existing installation ID, Python package, schema and historical
reports compatible. Use the human-facing name UT-Analysis. One project with no explicit mode routes
to audit; two projects preserve compare by default, and explicit full includes quality comparison.
An explicit compare/full request without B fails rather than silently degrading to audit.

Add neutral --project/--branch aliases and shared mode resolution. Move requirement-first analysis
into a dedicated Skill reference: authoritative scope/criteria → UT/assertion traces → actual execution
and coverage → prioritized gaps. Missing requirements remain evidence-insufficient; no default gates.
Existing report queries and incremental progress remain supporting workflows.

Extend the bundled synthetic demo to actually scan/run only one project in audit mode, read an
explicit synthetic acceptance document, and demonstrate sufficient/partial/uncovered requirements
even when every existing UT passes. Verify routing, single-project preparation, actual execution,
queryable requirement evidence, unchanged compare behavior, and the installed entrypoint.
No business project analysis or code changes are requested in this upgrade.
