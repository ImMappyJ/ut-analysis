# UT-Analysis

[中文](README.md) · [Installation](docs/installation.md) · [Usage](docs/usage.md) · [Changelog](CHANGELOG.md)

**Analyze unit tests against product requirements, identify important gaps, and track repairs.**

UT-Analysis is an installable Codex Skill that connects requirements, test code, assertions and execution evidence in a standalone interactive HTML report. Single-project analysis is the primary workflow; project and Git-branch comparisons are optional.

| Project information | Version / entry point |
| --- | --- |
| Skill | `0.7.1` · `$ut-analysis` |
| Report template / Schema | `1.3.0` / `1.1.0` |
| Default output | `docs/ut_result.html` in the caller's workspace |
| Runtime / License | Python 3.10+ · Standard library · [MIT](LICENSE) |

## Features and modes

| Mode | Input | Analysis |
| --- | --- | --- |
| `audit` | One project | Requirement traces, assertion quality, measured coverage and prioritized gaps |
| `compare` | Two projects or branches | Side-by-side goals, scenarios, inputs, assertions and execution results |
| `full` | Two projects and product goals | UT comparison plus requirement coverage and quality gates for both projects |

Without an explicit mode, one project selects `audit` and two select `compare`. Request `full` for combined analysis.

- **Requirement traceability:** link acceptance criteria to tests and assertion evidence; distinguish sufficient, partial, uncovered and uncertain coverage.
- **Evidence-based conclusions:** use measured coverage and explicit quality gates; missing evidence stays visible.
- **Isolated branch analysis:** explicit branches use separate Worktrees, preserving the original checkout and uncommitted changes.
- **Offline reports:** module and owner grouping, search, filters, pagination and expandable evidence. Matching and execution statuses remain separate.
- **Ongoing iteration:** query cards by test name or file, retrieve requirement/quality/repair context and incrementally synchronize repair notes.

## Installation

Requires Python **3.10+**, with no Python runtime dependencies. Go AST collection requires Go **1.18+**. Target tests need their own toolchains and dependencies.

### Windows PowerShell

```powershell
git clone https://github.com/ImMappyJ/ut-analysis.git UT-Analysis
Set-Location UT-Analysis
python scripts/install_skill.py --mode link
```

### Linux / macOS

```sh
git clone https://github.com/ImMappyJ/ut-analysis.git UT-Analysis
cd UT-Analysis
python3 scripts/install_skill.py --mode link
```

Link mode uses a Windows junction or Unix symlink. Choose `--mode copy` for an independent copy. The default destination is `$CODEX_HOME/skills`, or `~/.codex/skills` when unset.

Invoke `$ut-analysis` in Codex after installation. Open a new session if the current session has not discovered the skill. This project is distributed as a Skill/source checkout, not a PyPI package. See [installation details](docs/installation.md) for updates, conflicts and custom directories.

## Quick start

### 1. Analyze one project against its requirements

```text
$ut-analysis
Project: ./my-project
Requirements: ./docs/acceptance.md
Scope: ordering module
Trace existing UTs to acceptance criteria and prioritize assertion and scenario gaps.
```

No project B or hand-written JSON is required. The Agent interprets requirements and code; Python validates data, calculates statistics and gates, and renders reports. See [single-project analysis](references/single-project-analysis.md).

### 2. Compare projects or branches

```text
$ut-analysis
Mode: full
Project A: ./my-project
Branch A: main
Project B: ./my-project
Branch B: feature/refactor
Product goals: ./requirements/acceptance.md
Module owners: Example Owner Alpha owns ordering.
```

Use `compare` for UT comparison alone. A/B can refer to different repositories or the same repository. Branch choices are independent. Omitted branches use the current workspace, including recorded uncommitted changes.

### Inputs

| Parameter | Required | Meaning |
| --- | --- | --- |
| Project / Project A | Yes | Absolute/relative path or a uniquely identifiable workspace project |
| Project B | `compare` / `full` | Another project or version of the same repository |
| Mode | No | `audit`, `compare` or `full` |
| Branch A / B | No | Current workspace by default; explicit branches are isolated without automatic fetching |
| Product goals / Requirements | No | Natural language, PRD, specification, user stories or acceptance document paths |
| Scope | No | Entire project or selected modules, files or requirements; preserve exclusions and denominators |
| Coverage targets | No | Explicit thresholds or core-requirement rules; no invented mandatory defaults |
| Module owners | No | Natural-language module-to-owner mapping, including multiple owners |
| Output | No | Defaults to `docs/ut_result.html`; explicitly request replacement of an existing report |

## Example reports

| Example | Contents |
| --- | --- |
| [Single-project audit](examples/audit_report.html) | Requirement coverage, quality findings and missing evidence |
| [Project comparison](examples/sample_report.html) | Aligned cards, unilateral tests and assertion/scenario differences |
| [Combined analysis](examples/full_report.html) | Switch between Diff, requirements, coverage and quality |
| [Repair progress](examples/progress_report.html) | Changes, pending work, reasons and historical evidence |

Download the HTML and open it locally. No CDN or service is required. Static examples contain synthetic data and `NOT RUN` test results; runnable demos collect execution evidence separately.

![UT-Analysis comparison example](docs/images/report-preview.jpg)

## Continue from an existing report

### Query cards and context

```text
$ut-analysis
Report: ./docs/ut_result.html
Test file: tests/test_inventory.py
Project: A
Return all cards for this file with requirements, quality findings and repair progress.
```

Alternatively, provide a test name such as `test_reject_invalid`. Queries are read-only and do not scan source or execute tests. Ambiguous names return candidates.

```sh
python scripts/query_report.py report.html --file tests/test_inventory.py --project A
python scripts/query_context.py report.html --requirement REQ-INVALID --detail
python scripts/query_context.py report.html --section progress --progress ./docs/ut-progress
```

Context queries return paginated summaries by default. Use `--detail` for code, logs and evidence. See [card queries](references/card-query.md) and [context queries](references/context-query.md).

### Synchronize repair notes incrementally

Repair Markdown is synchronized by task into the caller's `docs/ut-progress/`. Unchanged notes require only a hash check; only changed tasks need renewed analysis. The repair-progress view shows what changed, what remains and why.

Repair records never replace historical execution results, semantic matches or quality gates. See [repair tracking](references/progress-tracking.md).

## Verification and local demos

Run from the repository root. On Linux/macOS, use `python3` if needed.

```sh
python -m unittest discover -s tests -v
python scripts/check_release.py
python scripts/validate_report.py examples/sample_report.html
python scripts/demo_e2e.py --mode audit --workspace .artifacts/audit-demo
python scripts/demo_e2e.py --workspace .artifacts/compare-demo
```

Demo directories must be empty. Demos copy and execute only bundled synthetic projects. Missing requirement coverage remains visible even if every test passes. Add `--without-owners --no-execution` to inspect owner-free and unexecuted cases.

GitHub Actions defines a Windows/Linux/macOS × Python 3.10/3.12 matrix. See [Actions](https://github.com/ImMappyJ/ut-analysis/actions) for remote results and [verification records](docs/verification.md) for historical local evidence.

## Scope and limitations

- Built-in Python/Go AST collection and unittest, Go JSON and JUnit runtime adapters. Other frameworks use native collection/reporters and the shared schema. Disclose dynamic-discovery and build-condition gaps.
- Count top-level entries and parameter templates once; record child instances separately. Two passing tests do not establish equivalent business behavior. Missing UTs do not prove missing functionality.
- Coverage comes from native artifacts: Go statement profiles, coverage.py, LCOV and Cobertura. Missing collection is not 0%; high coverage cannot cancel missing critical business scenarios.
- Execution is not sandboxed. Review dependencies and external effects before running tests. The Skill does not automatically rewrite business code, migrate tests, install dependencies or publish projects.
- Keep real business data, identities and logs in the caller's workspace. Public examples use synthetic data only.

## Documentation

| Topic | References |
| --- | --- |
| Usage and architecture | [CLI parameters](docs/usage.md) · [Architecture](docs/architecture.md) |
| Requirements and quality | [Traceability](references/requirement-traceability.md) · [Quality rules](references/quality-rules.md) · [Coverage collection](references/coverage-collection.md) |
| Comparison and versions | [Semantic matching](references/matching-rules.md) · [Git isolation](references/git-analysis.md) |
| Data and extensions | [Schema](references/report-schema.md) · [Framework adapters](references/framework-adapters.md) · [Template extension](references/template-extension.md) |
| Maintenance and license | [Changelog](CHANGELOG.md) · [MIT License](LICENSE) |
