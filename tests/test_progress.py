import copy
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

from ut_diff_report import progress
from ut_diff_report.core import load_data, render, ValidationError, validate_html
from ut_diff_report.card_query import get_ut_card, get_ut_cards

ROOT = Path(__file__).resolve().parents[1]


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.notes = self.root / 'docs/result.md'
        self.notes.parent.mkdir()
        self.notes.write_text('# Repairs\n\n## TASK-1\nAdded a test.\n\n## TASK-2\nKeep the difference.\n', encoding='utf-8')
        self.store = self.root / 'docs/ut-progress'
        self.report = render(load_data(ROOT / 'examples/sample_input.json'), workspace=self.root)

    def tearDown(self):
        self.temp.cleanup()

    def prepared(self):
        return progress.prepare_sync(self.notes, self.store, self.report, workspace=self.root)

    def commit(self, plan=None):
        plan = plan or self.prepared()
        annotations = {'document_sha256': plan['document_sha256'], 'base_revision': plan['base_revision'],
                       'removed': plan['removed'], 'sections': []}
        for s in plan['changed']:
            annotations['sections'].append({'key': s['key'], 'sha256': s['sha256'], 'items': [{
                'issue_id': s['key'], 'targets': [{'project': 'A', 'path': 'test_inventory.py', 'name': 'test_reject_invalid'}],
                'status': 'IMPLEMENTED', 'change': 'MODIFIED', 'summary': 'Assertion repaired.',
                'reason': 'Keep the expected validation behavior.', 'next_step': 'Verify current source.',
                'owner': 'Example owner', 'priority': 'P0', 'reported_at': '2026-01-01',
                'quote': s['text'].strip().splitlines()[-1],
                'verification': {'status': 'PASS', 'scope': 'Historical single-test run in the notes.'}}]})
        self.last_batch = copy.deepcopy(annotations)
        return progress.commit_sync(self.notes, self.store, self.report, annotations, workspace=self.root)

    def test_first_sync_no_change_and_one_changed_section(self):
        plan = self.prepared()
        self.assertEqual(len(plan['changed']), 2)
        self.commit(plan)
        self.assertEqual(self.prepared()['changed'], [])
        self.notes.write_text(self.notes.read_text() + 'Follow-up note.\n', encoding='utf-8')
        plan = self.prepared()
        self.assertEqual(len(plan['changed']), 1)
        self.assertEqual(plan['changed'][0]['key'], 'TASK-2')

    def test_query_is_summary_and_preserves_archived_result(self):
        self.commit()
        before = self.report.read_bytes()
        result = progress.get_ut_context(self.report, 'test_reject_invalid', progress_path=self.store)
        self.assertNotIn('code', result['baseline']['card']['left'])
        self.assertEqual(result['baseline']['card']['left']['result']['status'], 'NOT RUN')
        self.assertEqual(result['progress']['items'][0]['evidence_state'], 'DOCUMENT_ONLY')
        self.assertEqual(len(result['progress']['items']), 2)
        detailed = progress.get_ut_context(self.report, 'test_reject_invalid', progress_path=self.store, detail=True)
        self.assertIn('code', detailed['baseline']['card']['left'])
        self.assertEqual(before, self.report.read_bytes())

    def test_stale_and_removed_source_never_disappear(self):
        self.commit()
        self.notes.write_text('# Repairs\n## TASK-1\nChanged description.\n', encoding='utf-8')
        state = progress.load_progress(self.store)
        self.assertTrue(all(i['evidence_state'] == 'STALE' for i in state['items']))
        self.assertEqual(self.prepared()['removed'], ['TASK-2'])
        self.commit()
        state = progress.load_progress(self.store)
        self.assertEqual(len(state['history']), 1)
        self.assertTrue(any(i['source_state'] == 'REMOVED' for i in state['items']))

    def test_concurrent_or_changed_document_batch_is_rejected(self):
        plan = self.prepared()
        self.commit(plan)
        with self.assertRaises(ValidationError):
            self.commit(plan)
        plan = self.prepared()
        self.notes.write_text(self.notes.read_text() + 'new text', encoding='utf-8')
        with self.assertRaises(ValidationError):
            self.commit(plan)

    def test_render_overlay_keeps_baseline_counts_and_safe_text(self):
        self.commit()
        out = self.root / 'docs/updated.html'
        progress.render_progress_report(self.report, self.store, out)
        self.assertEqual(validate_html(out), validate_html(self.report))
        self.assertEqual(get_ut_card(out, 'test_reject_invalid')['card']['relation']['match'], 'PARTIAL')
        self.assertEqual(len(progress.get_ut_context(out, 'test_reject_invalid')['progress']['items']), 2)

    def test_different_report_binding_is_rejected(self):
        self.commit()
        data = load_data(ROOT / 'examples/sample_input.json')
        data['report_metadata']['run_id'] = 'another-branch'
        other = render(data, workspace=self.root, output='other.html')
        with self.assertRaises(ValidationError):
            progress.get_ut_context(other, 'test_reject_invalid', progress_path=self.store)

    def test_file_summary_and_old_full_api_remain_compatible(self):
        result = get_ut_cards(self.report, 'test_inventory.py', detail=False)
        self.assertTrue(all('code' not in (c['left'] or {}) for c in result['cards']))
        full = get_ut_cards(self.report, 'test_inventory.py')
        self.assertTrue(any('code' in (c['left'] or {}) for c in full['cards']))

    def test_duplicate_headings_and_path_escape_rejected(self):
        self.notes.write_text('## SAME\na\n## SAME\nb\n', encoding='utf-8')
        with self.assertRaises(ValidationError):
            self.prepared()
        with self.assertRaises(ValidationError):
            progress.prepare_sync(self.notes, self.store, self.report, workspace=self.root / 'outside')

    def test_notes_only_new_test_does_not_invent_baseline_card(self):
        self.commit()
        batch = self.last_batch
        for section in batch['sections']:
            section['items'][0]['targets'][0]['name'] = 'ExampleTests.test_added_later'
            section['items'][0]['targets'][0]['path'] = 'future/test_pending.py'
        other = self.root / 'docs/other-progress'
        progress.commit_sync(self.notes, other, self.report, batch, workspace=self.root)
        result = progress.get_ut_context(self.report, 'test_added_later', progress_path=other)
        self.assertEqual(result['baseline']['status'], 'NOT_FOUND')
        self.assertNotIn('card', result['baseline'])
        self.assertEqual(result['progress']['status'], 'FOUND')
        self.assertEqual(progress.get_ut_context(self.report, 'test_added_later', path='future\\test_pending.py', progress_path=other)['progress']['status'], 'FOUND')

    def test_invalid_quote_and_tampered_snapshot_rejected(self):
        self.commit()
        batch = self.last_batch
        batch['sections'][0]['items'][0]['quote'] = 'Invented source sentence'
        with self.assertRaises(ValidationError):
            progress.commit_sync(self.notes, self.root / 'docs/other-progress', self.report, batch, workspace=self.root)
        state = json.loads((self.store / 'state.json').read_text())
        snapshot = self.store / 'snapshots' / (state['revision'] + '.json')
        snapshot.write_text('{}')
        with self.assertRaises(ValidationError):
            progress.load_progress(self.store)

    def test_source_script_text_is_escaped_in_offline_report(self):
        self.notes.write_text('## TASK-1\n</script><script>alert(1)</script>\n', encoding='utf-8')
        self.commit()
        out = self.root / 'safe.html'
        progress.render_progress_report(self.report, self.store, out)
        validate_html(out)
        self.assertNotIn('</script><script>alert(1)</script>', out.read_text(encoding='utf-8'))

    def test_nested_shorter_fence_does_not_create_fake_tasks(self):
        self.notes.write_text('## TASK-1\n````markdown\n```\n## NOT-A-TASK\n```\n````\n## TASK-2\nReal task\n', encoding='utf-8')
        self.assertEqual([s['key'] for s in self.prepared()['changed']], ['TASK-1', 'TASK-2'])

    def test_demo_and_cli_summary_commit_prepare_contract(self):
        target = self.root / 'demo'
        run = subprocess.run([sys.executable, str(ROOT / 'scripts/demo_progress.py'), '--workspace', str(target)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(run.returncode, 0, run.stderr)
        validate_html(target / 'docs/ut_progress_report.html')
        prepared = subprocess.run([sys.executable, str(ROOT / 'scripts/sync_progress.py'), 'prepare', '--workspace', str(target)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertFalse(json.loads(prepared.stdout)['needs_analysis'])
        query = subprocess.run([sys.executable, str(ROOT / 'scripts/query_report.py'), str(target / 'docs/ut_result.html'), '--name', 'test_reject_invalid', '--progress', str(target / 'docs/ut-progress')], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(query.returncode, 0, query.stderr)
        result = json.loads(query.stdout)
        self.assertNotIn('code', result['baseline']['card']['left'])
        self.assertEqual(result['progress']['status'], 'FOUND')
        again = subprocess.run([sys.executable, str(ROOT / 'scripts/demo_progress.py'), '--workspace', str(target)], capture_output=True)
        self.assertEqual(again.returncode, 2)

    def test_explicit_annotation_correction_preserves_original_revision(self):
        self.commit()
        plan = progress.prepare_sync(self.notes, self.store, self.report, workspace=self.root, refresh_sections=['TASK-1'])
        batch = {'base_revision': plan['base_revision'], 'document_sha256': plan['document_sha256'], 'removed': [],
                 'refresh_sections': ['TASK-1'], 'correction_reason': 'Correct a mistaken priority classification.',
                 'sections': [self.last_batch['sections'][0]]}
        batch['sections'][0]['items'][0]['priority'] = 'P1'
        progress.commit_sync(self.notes, self.store, self.report, batch, workspace=self.root)
        state = progress.load_progress(self.store)
        self.assertEqual(state['items'][0]['priority'], 'P1')
        self.assertEqual(state['history'], [plan['base_revision']])

    def test_derived_report_cannot_change_results_while_carrying_baseline_pointer(self):
        self.commit()
        out = self.root / 'derived.html'
        progress.render_progress_report(self.report, self.store, out)
        from ut_diff_report.card_query import _read_report
        from ut_diff_report.core import view_html
        view = _read_report(out)[2]
        view['records'][0]['result']['status'] = 'PASS'
        out.write_text(view_html(view), encoding='utf-8')
        with self.assertRaises(ValidationError):
            progress.get_ut_context(out, 'test_reject_invalid', progress_path=self.store)

    def test_legacy_migration_requires_physical_original_baseline(self):
        self.commit()
        out = self.root / 'derived.html'
        progress.render_progress_report(self.report, self.store, out)
        state = json.loads((self.store / 'state.json').read_text())
        state.pop('revision')
        state.pop('baseline_data_sha256')
        raw = json.dumps(state, ensure_ascii=False).encode('utf-8')
        revision = progress.digest(raw)
        (self.store / 'snapshots' / (revision + '.json')).write_bytes(raw)
        (self.store / 'state.json').write_text(json.dumps(dict(state, revision=revision)), encoding='utf-8')
        from ut_diff_report.card_query import _read_report
        from ut_diff_report.core import view_html
        view = _read_report(out)[2]
        view['meta']['run_id'] = 'forged-run'
        view['records'][0]['result']['status'] = 'PASS'
        out.write_text(view_html(view), encoding='utf-8')
        with self.assertRaises(ValidationError):
            progress.prepare_sync(self.notes, self.store, out, workspace=self.root)
        plan = self.prepared()
        batch = {'base_revision': plan['base_revision'], 'document_sha256': plan['document_sha256'], 'removed': [], 'sections': []}
        progress.commit_sync(self.notes, self.store, self.report, batch, workspace=self.root)
        self.assertEqual(progress.load_progress(self.store)['baseline_data_sha256'], plan['baseline_data_sha256'])
