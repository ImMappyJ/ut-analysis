# Incremental repair notes and summary-first queries (0.5.0)

Use this route when the user supplies a repair Markdown file or asks to incorporate later work
into an existing report. The fixed template now has a separate repair-progress tab. This route
does not rescan repositories, run tests, recompute matches or change historical result counts.

## Three-step sync

All paths below resolve relative to the caller workspace, not the Skill source checkout.

```text
python <skill-root>/scripts/sync_progress.py prepare --workspace <workspace> --notes docs/result.md --report docs/ut_result.html
```

The response contains ONLY changed top-level `##` task sections, their verbatim text and hashes,
the document hash, base revision and removed keys. Stable task labels before a colon survive title
edits. Duplicate labels are rejected. Code fences do not create headings. Unchanged sections are
omitted: if needs_analysis=false, do not ask the model to re-read/reinterpret the full document.
Ordinary introduction text outside task sections is not a repair item; changes to it still change
the document hash. An empty document or removed section does not imply the issue was resolved.

For each changed section, the Agent prepares exactly one section entry with all its current items.
Read the entire changed task, including appended implementation updates, rather than only its title.
Preserve earlier candidate/implementation stages in optional timeline entries with exact quotes.
Unchanged task annotations are reused. Semantic interpretation is not a regex/keyword completion rule.
Author a fresh annotations JSON file in caller docs/ut-progress/imports/:

```json
{
  "document_sha256": "hash from prepare",
  "base_revision": null,
  "removed": [],
  "sections": [{
    "key": "TASK-1",
    "sha256": "section hash from prepare",
    "items": [{
      "issue_id": "TASK-1-validation",
      "targets": [{"project": "A", "path": "test_inventory.py", "name": "test_reject_invalid"}],
      "status": "IMPLEMENTED",
      "change": "MODIFIED",
      "summary": "The invalid-input assertion was repaired.",
      "reason": "The old assertion checked the wrong exception field.",
      "next_step": "Verify the current source snapshot before reusing the historical result.",
      "owner": "Unassigned",
      "priority": "UNCLASSIFIED",
      "reported_at": "2026-01-01",
      "quote": "A verbatim excerpt from the changed section.",
      "verification": {"status": "PASS", "scope": "The notes report one historical targeted run; no new test run."}
    }]
  }]
}
```

For missing dates use `unknown`, missing priority UNCLASSIFIED and missing owner Unassigned.
Do not invent missing names or paths: an unimplemented goal can have targets=[]. One change can
reference several UTs; the UI counts registered items, not code edits or top-level UT totals.
Use one item for a shared import repair. Do not count subtests/repeated runs as new UTs.

```text
python <skill-root>/scripts/sync_progress.py commit --workspace <workspace> --annotations docs/ut-progress/imports/batch.json
python <skill-root>/scripts/sync_progress.py render --workspace <workspace> --output docs/ut_progress_report.html
```

Commit validates exact source quotes, all changed keys, document/section hashes and optimistic base
revision under an exclusive lock. It writes a content-addressed immutable snapshot and atomically
updates state.json. All prior snapshots remain; removed records stay visible as stale/removed.
Unexpected concurrent edits or a live lock cause failure instead of silently overwriting another writer.
No automatic lock deletion or partial semantic merges. No background watcher, polling or model calls.
If nothing changed, commit is idempotent. State/snapshot integrity mismatches are rejected.

To correct an earlier interpretation without editing the source notes, prepare with
`--refresh-section TASK-1`. Include `refresh_sections: ["TASK-1"]` and a nonempty
`correction_reason` in the annotation batch. Re-annotate the complete selected section; the
previous snapshot and correction reason remain traceable. This is an explicit correction,
not a reason to re-analyze unchanged sections on every sync.

## Scope, freshness and rendering

The ledger binds to one exact baseline report hash, including its original A/B source contexts.
Different reports/branches require a new ledger or an explicitly reviewed migration; no automatic
cross-branch inheritance of fixed status. A derived report records baseline_report_sha256 and keeps
the baseline's generated_at, inventory, matches, runtime observations and quality judgments intact.
The presentation version is recorded separately. Paths in ledger configuration are relative and
validated within the caller workspace; queries do not follow evidence links or execute commands.
The ledger also stores `baseline_data_sha256`, a fingerprint of the embedded baseline evidence.
A derived report with a copied ancestor pointer but altered test results or run metadata is rejected.
An older ledger without this fingerprint must first be committed against its exact preserved
baseline, even if there are no changed note sections; do not infer integrity from the pointer alone.

Rendering requires a different source/output path. If updating docs/ut_result.html is authorized,
first preserve an exact baseline copy under docs/ut-diff/<run>/baseline.html, then render from that
copy to docs/ut_result.html with --replace. Never silently overwrite a baseline or an existing output.

Annotations are DOCUMENT_ONLY: they are evidence of what the document says, not confirmation that
logs are intact, source has not changed, product requirements were met or the current UT passes.
The separate verification.status is labelled as the document's historical statement.
Current notes hash changes cause STALE/CHANGED; removed source remains STALE/REMOVED. Artifact/source
execution verification is still the normal explicit workflow, not part of note synchronization.
Pure embedded-report queries read a generation-time snapshot; only explicit --progress reads the
configured notes file to check freshness. Do not claim an offline HTML notices later file edits live.

Progress states: PLANNED, IN_PROGRESS, IMPLEMENTED, BLOCKED, DEFERRED, ACCEPTED_DIFFERENCE, CONFLICT.
Code-change labels: UNKNOWN, UNCHANGED, MODIFIED, ADDED, REMOVED, REVERTED.
Every item requires a concrete reason and next step. No record means UNRECORDED, not unchanged.
One implemented fix may coexist with a separate unresolved issue on the same test.
Changed section revisions replace its active interpretation while retaining the prior snapshot;
cross-task conflicting accounts are displayed separately, not automatically collapsed to latest-wins.

## Query without sending full logs to the model

```text
python <skill-root>/scripts/query_report.py docs/ut_result.html --name test_reject_invalid --progress docs/ut-progress
python <skill-root>/scripts/query_report.py docs/ut_result.html --file test_inventory.py --project A --progress docs/ut-progress
python <skill-root>/scripts/query_report.py docs/ut_result.html --id A-invalid --detail --progress docs/ut-progress
```

CLI defaults to summary: identity, goal, match/result state and progress, no code/diff/raw logs.
Use --detail only for the selected card(s) when needed. --output writes complete requested data to
a fresh file; the model need only see the returned path/counts rather than the full JSON.
Existing Python get_ut_card/get_ut_cards default to full data for compatibility; detail=False requests
summary. get_ut_context defaults to summary, returns baseline and progress separately, and supports
name/ID or file_path. Ambiguous baseline names remain AMBIGUOUS; no automatic first-card selection.
If the baseline has no new UT but the ledger does, baseline stays NOT_FOUND and progress can be FOUND.

The report must not be treated as a live inventory. Context matching uses project+path+exact name,
never fuzzy name similarity. Missing or ambiguous associations are preserved for inspection.
The page supports status/module/owner/priority/evidence/association filters, search, 30-item pagination,
source excerpts and optional timeline; baseline cards link to their progress and back.

## Distribution and limitations

Runtime uses only Python standard library. Private notes and ledgers remain in caller workspaces;
docs/ut-progress and reports are excluded from Skill copies. Examples are synthetic.
Token savings arise from limiting model-visible text, not eliminating filesystem reads or guaranteeing
a fixed token percentage. The initial semantic import still needs Agent reading and judgment.
The original design has broader optional future work (artifact verification, arbitrary report rebinding,
fine-grained subtask diffs); those are not silently claimed by this version.
