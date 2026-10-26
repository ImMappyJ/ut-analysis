# Semantic matching and accounting

Read bodies, fixture setup, relevant helpers, inputs and assertions. Record source locations.
Different names may verify the same behavior; equal source may invoke changed helpers.

| Status | Evidence required |
| --- | --- |
| EXACT | Same business scenario, input domain, expectations and relevant helper semantics |
| PARTIAL | Common goal, but meaningful condition, boundary, assertion or granularity differences |
| A_ONLY / B_ONLY | No supportable counterpart; retain other-side blank placeholder |

Uncertain relationships remain unilateral. Formatting/naming alone does not prevent exact correspondence.
Zero-quantity versus zero-plus-negative-quantity checks are partial even if both PASS.
`assertEqual([], [])` cannot establish an actual catalog operation or empty response.

Normalize business modules using behavior, not directory names. Store A/B scopes and mapping evidence.
Owners attach to modules; shared ownership can overlap in owner views while global totals stay unique.
P0 covers contextually critical flows, authorization, data integrity or charging/state rules;
P1 covers less critical behavior. Store a reason; leave 未评级 when evidence is insufficient.
Ownership indicates responsibility only, never completed review.

Count one top-level static test function/method/template. Parameter instances and runtime subtests
are nested evidence; class/suite containers are not extra UT. Go TestSuite is one main entry,
with framework methods/subtests and their source locations retained beneath it when identifiable.
Reconcile dynamic/inherited tests with native collection, preserving factory/source location and
collector identity. Never guess unexecuted dynamic instance counts from loop syntax.
Lifecycle/setup, benchmarks/examples/fuzz and integration/E2E belong in evidence/appendix.

Every UT appears exactly once in the main match partition, including unilateral rows.
`related_test_ids` captures one-to-many granularity without adding counts.

Runtime is independent of matching. Missing execution is NOT RUN with reason; unstarted entries after
build/collection failure are NOT RUN with package diagnostics. A started test's error is ERROR where
the framework distinguishes it. Native Go fail events map to FAIL; do not guess a universal Go ERROR.

SAME/DIFFERENT compares observed parent status and explicit child scenario-key/status sets.
Missing run, or equal parent status with unmapped child scenarios, gives UNKNOWN. Different parent
statuses are DIFFERENT regardless of child mapping. Unilateral rows are excluded from agreement totals.
Logs/duration do not determine semantic or status equality. Preserve prior invocations; a successful
rerun does not establish that the batch/package passed. Code coverage needs separate measured evidence.
