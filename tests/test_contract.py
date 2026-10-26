import copy
import json
from pathlib import Path
import tempfile
import unittest

from ut_diff_report.core import ValidationError, load_data, render, summarize, validate, validate_html, view_data

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = json.loads((ROOT / 'examples/sample_input.json').read_text(encoding='utf-8'))

    def data(self):
        return copy.deepcopy(self.sample)

    def test_sample_and_partition(self):
        d = self.data()
        validate(d)
        s = summarize(d)
        self.assertEqual(s['UT'], {'A': 3, 'B': 3})
        self.assertEqual(s['matching'], {'EXACT': 1, 'PARTIAL': 1, 'A_ONLY': 1, 'B_ONLY': 1})
        self.assertEqual(sum(s['results']['A'].values()), 3)
        self.assertEqual(sum(s['results']['B'].values()), 3)

    def test_duplicate_and_missing_match_rejected(self):
        for mutation in ('duplicate', 'missing'):
            with self.subTest(mutation=mutation):
                d = self.data()
                if mutation == 'duplicate':
                    d['matches'].append({**d['matches'][0], 'id': 'another'})
                else:
                    d['matches'].pop()
                with self.assertRaises(ValidationError):
                    validate(d)

    def test_pass_without_runtime_evidence_rejected(self):
        d = self.data()
        r = d['execution_results'][0]
        r['status'] = 'PASS'
        r['command'] = []
        with self.assertRaises(ValidationError):
            validate(d)

    def test_missing_reason_unknown_reference_and_stale_summary(self):
        for field in ('reason', 'reference', 'summary'):
            with self.subTest(field=field):
                d = self.data()
                if field == 'reason':
                    d['execution_results'][0].update(status='NOT RUN', reason='')
                elif field == 'reference':
                    d['matches'][0]['a'] = 'nonexistent'
                else:
                    d['summary'] = {'UT': {'A': 999}}
                with self.assertRaises(ValidationError):
                    validate(d)

    def test_execution_not_inferred_from_matching(self):
        d = self.data()
        d['execution_results'] = []
        s = summarize(d)
        self.assertEqual(s['results']['A']['NOT RUN'], 3)
        self.assertEqual(s['execution']['SAME'], 0)

    def test_nested_source_evidence_and_dates_are_validated(self):
        for mutation in ('subtest', 'date', 'priority'):
            with self.subTest(mutation=mutation):
                d = self.data()
                if mutation == 'subtest':
                    d['test_cases'][0]['subtests'] = [{}]
                elif mutation == 'date':
                    d['report_metadata']['generated_at'] = 'yesterday'
                else:
                    d['modules'][0]['priority_reason'] = ''
                with self.assertRaises(ValidationError):
                    validate(d)

    def test_atomic_replace_and_deterministic_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            out = render(self.data(), workspace=workspace)
            self.assertEqual(out, workspace.resolve() / 'docs/ut_result.html')
            original = out.read_bytes()
            with self.assertRaises(FileExistsError):
                render(self.data(), workspace=workspace)
            render(self.data(), workspace=workspace, replace=True)
            self.assertEqual(original, out.read_bytes())
            bad = self.data()
            bad['matches'] = []
            with self.assertRaises(ValidationError):
                render(bad, workspace=workspace, replace=True)
            self.assertEqual(original, out.read_bytes())
            validate_html(out)

    def test_injection_and_no_owners(self):
        d = self.data()
        payload = '</script><img src=x onerror=alert(1)>\u2028& __REPORT_TITLE__'
        d['test_cases'][0]['goal'] = payload
        d['owners'] = []
        for module in d['modules']:
            module['owner_ids'] = []
        with tempfile.TemporaryDirectory() as folder:
            p = render(d, workspace=Path(folder))
            content = p.read_text(encoding='utf-8')
            self.assertNotIn(payload, content)
            self.assertIn('\\u003c/script', content)
            validate_html(p)

    def test_json_rejects_duplicates_and_non_finite(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'bad.json'
            for raw in ('{"a":1,"a":2}', '{"a":NaN}'):
                p.write_text(raw, encoding='utf-8')
                with self.assertRaises(ValidationError):
                    load_data(p)

    def test_case_ids_cannot_collide_with_static_or_detail_dom_ids(self):
        d = self.data()
        d['matches'][0]['id'] = 'rows'
        d['matches'][2]['id'] = 'rows-detail'
        pairs = view_data(d)['pairs']
        ids = [p['id'] for p in pairs]
        detail_ids = ['detail-' + p['id'] for p in pairs]
        self.assertNotIn('rows', ids)
        self.assertEqual(len(set(ids + detail_ids)), len(ids + detail_ids))


if __name__ == '__main__':
    unittest.main()
