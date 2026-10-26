import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ut_diff_report.core import load_data, render, ValidationError
from ut_diff_report.report_context import get_report_context, get_requirements, get_quality, get_repair_progress

ROOT = Path(__file__).resolve().parents[1]


class ReportContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = load_data(ROOT / 'examples/full_input.json')
        self.report = render(self.data, workspace=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_requirement_detail_returns_sources_criteria_and_two_sided_traces(self):
        r = get_requirements(self.report, requirement_id='REQ-INVALID', detail=True)
        item = r['requirements']['items'][0]
        self.assertEqual(len(item['requirement']['criteria']), 2)
        self.assertEqual({t['project_id'] for t in item['traces']}, {'A', 'B'})
        self.assertTrue(item['sources'][0]['excerpt'])
        self.assertTrue(item['traces'][0]['assertion_evidence'])
        self.assertEqual({t['id'] for t in r['tests']['items']}, {'A-invalid', 'B-invalid'})

    def test_file_and_project_do_not_leak_opposite_side_quality(self):
        r = get_report_context(self.report, file_path='test_inventory.py', project='A')
        self.assertEqual({t['project_id'] for i in r['requirements']['items'] for t in i['traces']}, {'A'})
        self.assertEqual(set(r['quality']['projects']), {'A'})
        self.assertEqual(r['quality']['scope'], 'PROJECT_WIDE_SNAPSHOT')
        self.assertFalse(r['quality']['projects']['A']['coverage']['collected'])
        self.assertNotIn('code', r['tests']['items'][0])

    def test_untraced_requirement_remains_discoverable_without_fake_test(self):
        req = copy.deepcopy(self.data['quality']['requirements'][0])
        req.update(id='REQ-UNTRACED', applicable_projects=['B'], applicability_evidence=['Synthetic B-only scope'])
        self.data['quality']['requirements'].append(req)
        self.report = render(self.data, workspace=self.root, replace=True)
        r = get_requirements(self.report, requirement_id='REQ-UNTRACED', project='B')
        self.assertEqual(r['requirements']['total'], 1)
        self.assertEqual(r['requirements']['items'][0]['traces'], [])
        self.assertEqual(r['tests']['total'], 0)
        self.assertEqual(get_requirements(self.report, requirement_id='REQ-UNTRACED', project='A')['requirements']['total'], 0)

    def test_missing_quality_is_not_empty_success_or_zero_coverage(self):
        report = render(load_data(ROOT/'examples/sample_input.json'), workspace=self.root, replace=True)
        r = get_quality(report)
        self.assertEqual(r['quality']['availability'], 'NOT_AVAILABLE')
        self.assertEqual(r['requirements']['availability'], 'NOT_AVAILABLE')
        self.assertEqual(r['quality']['projects'], {})

    def test_issue_lookup_module_scope_and_uncertainty_preserved(self):
        report = render(load_data(ROOT/'examples/audit_input.json'), workspace=self.root, replace=True)
        r = get_quality(report, issue_id='Q-CONSTANT', module='auxiliary', detail=True)
        issue = r['quality']['issues']['items'][0]
        self.assertEqual(issue['certainty'], 'suspected')
        self.assertTrue(issue['evidence'])
        self.assertEqual(r['requirements']['total'], 0)
        self.assertEqual(r['tests']['items'][0]['id'], 'A-catalog')
        empty = get_quality(report, issue_id='Q-CONSTANT', module='not-a-module')
        self.assertEqual(empty['quality']['issues']['total'], 0)

    def test_summary_has_links_but_detail_has_evidence(self):
        summary = get_report_context(self.report, ut_name='test_reject_invalid')
        detail = get_report_context(self.report, ut_name='test_reject_invalid', detail=True)
        self.assertNotIn('assertion_evidence', summary['requirements']['items'][0]['traces'][0])
        self.assertIn('assertion_evidence', detail['requirements']['items'][0]['traces'][0])
        self.assertIn('source', summary)
        self.assertTrue(summary['requirements']['items'][0]['sources'][0]['reference'])

    def test_pagination_and_unknown_selectors(self):
        r = get_requirements(self.report, limit=1)
        self.assertEqual(r['requirements']['total'], 2)
        self.assertEqual(r['requirements']['next_offset'], 1)
        other = get_requirements(self.report, limit=1, offset=1)
        self.assertNotEqual(r['requirements']['items'], other['requirements']['items'])
        self.assertEqual(get_requirements(self.report, requirement_id='REQ-no')['requirements']['total'], 0)
        with self.assertRaises(ValidationError):
            get_report_context(self.report, project='C')
        with self.assertRaises(ValidationError):
            get_report_context(self.report, file_path='test_inventory.py', ut_name='x')

    def test_ambiguous_ut_never_expands_all_candidate_evidence(self):
        t = copy.deepcopy(self.data['test_cases'][0])
        t.update(id='A-other', path='other/test_inventory.py')
        self.data['test_cases'].append(t)
        self.data['matches'].append({'id':'other','a':t['id'],'b':None,'status':'A_ONLY','evidence':['Synthetic']})
        report = render(self.data, workspace=self.root, replace=True)
        r = get_report_context(report, ut_name=t['name'])
        self.assertEqual(r['status'], 'AMBIGUOUS')
        self.assertNotIn('requirements', r)

    def test_progress_embedded_and_live_staleness_and_new_only_test(self):
        from scripts.demo_progress import demo
        report = demo(self.root/'demo')
        r = get_repair_progress(report, ut_name='test_future_boundary')
        self.assertEqual(r['progress']['total'], 1)
        self.assertEqual(r['progress']['freshness'], 'EMBEDDED_SNAPSHOT')
        self.assertEqual(r['tests']['total'], 0)
        notes = self.root/'demo/docs/result.md'
        notes.write_text(notes.read_text(encoding='utf-8')+'changed\n', encoding='utf-8')
        live = get_repair_progress(report, progress_path=self.root/'demo/docs/ut-progress', ut_name='test_future_boundary')
        self.assertTrue(live['progress']['needs_sync'])
        self.assertEqual(live['progress']['items'][0]['evidence_state'], 'STALE')

    def test_cli_output_is_read_only_and_fresh_file_only(self):
        before = hashlib.sha256(self.report.read_bytes()).hexdigest()
        output = self.root/'context.json'
        command = [sys.executable,str(ROOT/'scripts/query_context.py'),str(self.report),'--section','requirements',
                   '--requirement','REQ-INVALID','--detail','--output',str(output)]
        run = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['requirements']['total'], 1)
        self.assertEqual(subprocess.run(command,capture_output=True).returncode, 2)
        self.assertEqual(hashlib.sha256(self.report.read_bytes()).hexdigest(), before)
