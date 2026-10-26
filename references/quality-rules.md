# Evidence-based quality assessment

Agent: interpret requirements, review test intent/assertions and assess risk.
Python: validate references, count unique requirements, compare measured metrics and evaluate explicit gates.
Do not let a heuristic or numeric score replace the evidence discussion.

Review only business-relevant categories: normal flow, invalid/missing input, dependency failure/business
conflict, boundary conditions, state/duplicate/illegal transitions, idempotence and required authorization/
data isolation. Some modules have no state/security requirement; do not invent one. Mock usage alone is not
a quality defect. Missing direct assertions can hide helper assertions; inspect before drawing conclusions.
Suspected weak assertions/duplicates are review leads, not proof the UT is wholly ineffective.
Confirmed findings need source review, execution or authorized mutation evidence; heuristic-only confirmation
is rejected. A confirmed product conflict must reference authoritative acceptance criteria.

## Three configurable gate layers

1. `policy.code[]`: metric/minimum/mandatory/basis, optional project IDs and module ID.
   No default percentage threshold. Use actual covered/total counts. Uncollected, zero denominator or mixed/
   unknown test scope produces INSUFFICIENT EVIDENCE for a pure UT target, never an invented 0%.
2. `policy.requirements`: core_must_be_sufficient and/or minimum_sufficient_percent, mandatory/basis.
   Core means explicit P0 requirements. Partial/uncovered mandatory core is FAIL; unknown core is insufficient.
   Ratio gates use lower/upper bounds when some units are unknown: a definite shortfall can fail, an undecidable
   threshold remains insufficient. Use unique requirement IDs, not test counts.
3. `policy.effectiveness`: no_confirmed_high_risk, mandatory/basis.
   Confirmed high-risk findings fail; suspected high-risk or incomplete reviewed P0 UT scope is insufficient.
   Nonblocking issues warn. An empty issue list without explicit reviewed IDs is not evidence of a completed review.

All policy bases must cite user targets or approved acceptance standards. Mandatory means the user/standard
actually required it, not an AI-selected organizational rule. Multiple metrics/modules/projects can have different
explicit targets. High coverage never cancels another failed gate. Mutation collection needs user authorization.

Overall order: any mandatory FAIL → FAIL; missing product evidence/configuration or unknown mandatory evidence →
INSUFFICIENT EVIDENCE; satisfied mandatory gates with nonblocking findings → WARN; otherwise PASS.
PASS means the listed quality gates, not product release approval or complete absence of defects.
Show configured pass/fail/warn/insufficient checks and reasons; no opaque composite score.

Schema: `references/quality.schema.json`; canonical fields: sources, requirements, traces, issues, coverage,
reviewed_test_ids, policy. `evaluate_quality.py` reproduces the judgment from this evidence.
