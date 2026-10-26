# Framework collection and execution

Built-in helpers cover Python AST, Go AST, unittest, Go JSON and JUnit XML. They support the Agent
workflow; they are not a universal framework or a semantic matcher. Resolve skill-root from SKILL.md.

## Python

```text
python <skill-root>/scripts/scan_project.py <project-A> --workspace <workspace> --id A --language python --output docs/ut-diff/<run>/A-inventory.json
python <skill-root>/scripts/run_tests.py --project <project-A> --artifacts <workspace>/docs/ut-diff/<run>/A-run --framework unittest
```

AST scanning never imports the project. It identifies unittest/pytest candidates, assertions,
parameter decorators and subTest callsites. Inspect custom discovery rules and reconcile inheritance,
decorators/dynamic tests with native collection; AST candidates alone do not prove completeness.
Unittest runner discovers test*.py by default (--pattern overrides), records successful subTests,
FAIL/ERROR/SKIP, and treats expected failure as SKIP with reason. Discovery/fixture errors may produce
framework error holders; map affected unstarted entries to NOT RUN without inventing PASS.

For installed pytest use native collection (`python -m pytest --collect-only -q`) and an audited
`python -m pytest --junitxml=<fresh-evidence.xml> ...` through --framework command.
Do not silently install plugins. Preserve instance node IDs and relate them to static templates from source.

## Go

```text
python <skill-root>/scripts/scan_project.py <project-B> --workspace <workspace> --id B --language go --output docs/ut-diff/<run>/B-inventory.json
python <skill-root>/scripts/run_tests.py --project <project-B> --artifacts <workspace>/docs/ut-diff/<run>/B-run --framework go -- go test -json -count=1 ./...
```

Go 1.18+ AST scanner never imports/initializes target packages. It inventories all _test.go build-tag
branches; runtime covers only selected GOOS/GOARCH/tags. Retain other branches NOT RUN with reasons.
Evidence includes TestMain, suite/helper methods, t.Run, assertions, table candidates, globals and positions.
Resolve helper behavior and suite-method counting explicitly. For actual gomonkey dependencies inspect
project commands and consider -gcflags=all=-N -l; never assume a universal host/WSL/toolchain requirement.
No individual event after a build failure means NOT RUN with package diagnostics. -count=1 avoids Go cache.

## Other languages and mixed frameworks

Use native discovery/listing and supported reporters (Jest/Vitest JSON, JVM/.NET/Python JUnit, etc.).
Inspect installed configuration instead of guessing flags. Agent reads source and writes canonical data;
no built-in scanner claims completeness for an unsupported language. Record limitations and NOT RUN if needed.
Mixed-language projects use the same schema and business-semantic matching.

run_tests.py --framework command -- <explicit argv> captures actual invocation provenance;
optional --junit <xml> imports observed instances. XML alone does not prove a fresh run.
The wrapper passes process environment without printing it; tests can still access credentials/network.
Audit external effects first; this wrapper is not a security sandbox. Keep real evidence in the caller workspace.
