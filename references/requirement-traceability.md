# Product requirements and UT traceability

Only explicit user descriptions or clearly authoritative PRD/specification/acceptance/user-story sources
establish product requirements. Search only the authorized workspace or provided document paths. Record
source ID, type, exact reference (path/lines or user message), excerpt and authority. Implementation and UT
are supporting technical evidence, never a substitute for an authoritative requirement.

Create unique, normalized requirement IDs and distinct acceptance criterion IDs. Extract actual normal,
error, boundary, state and security conditions only when present in the source. Do not invent rules for
ambiguous/conflicting/untestable requirements; retain them with testability status and UNKNOWN traces.

Each `(requirement_id, project_id)` has at most one trace. A full report uses the same requirement IDs for
both projects, rather than comparing unrelated requirement percentages. Missing traces are UNKNOWN.
Statuses:

- SUFFICIENT: every stated criterion has effective assertion evidence and no known missing condition.
- PARTIAL: a relevant test exists, but significant conditions/expectations/assertions are missing.
- UNCOVERED: no supportable UT target found; retain the inventory/search evidence for this statement.
- UNKNOWN: unreliable requirements, unresolved test/helper meaning or missing evidence prevents judgment.

Store actual UT IDs and assertion path/line/code with criterion references. Test names, successful calls,
Mock calls, code execution or passing status alone cannot establish requirement coverage. SUFFICIENT
requires all criteria linked to assertions marked valid by source review; the validator checks references,
not semantic truth. Agent must inspect helpers and actual control flow before marking an assertion effective.
Show runtime status separately; a design-coverage judgment is not proof that the product passed acceptance.

Record missing scenarios and a clear reason. Issues distinguish product conflict (requires authoritative
criteria), insufficient tests and uncertainty. Constant assertions may establish only a technical identity,
not an unseen business call. No product evidence means code-level findings only, with insufficient alignment.

Denominator: unique reliable, testable requirement units. Numerator: units with SUFFICIENT traces.
Never divide UT count by requirement count. Ambiguous requirements are displayed and counted as unknown
but excluded from a falsely precise verifiable-requirement denominator. Missing runtime is never replaced
with a manufactured PASS. Coverage of requirements, measured code coverage and runtime are separate axes.

Explicit product scope can restrict a requirement to `applicable_projects`, with `applicability_evidence`.
The default is all analyzed projects. A requirement proven inapplicable to the other project is displayed as
not applicable and excluded from its denominator, not marked as missing coverage. Do not infer non-applicability
from a missing implementation or test. Shared applicable IDs remain directly comparable in full mode.
