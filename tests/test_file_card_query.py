import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ut_diff_report import card_query
from ut_diff_report.core import load_data, render, view_data, ValidationError

ROOT = Path(__file__).resolve().parents[1]


class FileCardQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = load_data(ROOT / 'examples/sample_input.json')
        self.path = self.data['test_cases'][0]['path']

    def tearDown(self):
        self.temp.cleanup()

    def report(self):
        return render(self.data, workspace=self.root, replace=True)

    def test_all_cards_deduplicate_pairs_and_keep_both_sides(self):
        report = self.report()
        before = hashlib.sha256(report.read_bytes()).hexdigest()
        result = card_query.get_ut_cards(report, self.path)
        expected = [p for p in view_data(self.data)['pairs'] if any(
            t['id'] in (p.get('a'), p.get('b')) and t['path'] == self.path
            for t in self.data['test_cases'])]
        self.assertEqual(result['status'], 'FOUND')
        self.assertEqual(result['card_count'], len(expected))
        self.assertEqual(len({c['id'] for c in result['cards']}), len(expected))
        paired = next(c for c in result['cards'] if c['left'] and c['right'])
        self.assertEqual(paired['left']['result']['status'], 'NOT RUN')
        self.assertIn('locator', paired)
        self.assertEqual(hashlib.sha256(report.read_bytes()).hexdigest(), before)

    def test_project_filter_preserves_other_side_at_different_path(self):
        target = next(t for t in self.data['test_cases'] if t['id'] == 'B-invalid')
        target['path'] = 'other/test_moved.py'
        result = card_query.get_ut_cards(self.report(), target['path'], project='B')
        self.assertEqual(result['card_count'], 1)
        self.assertEqual(result['matched_test_count'], 1)
        self.assertEqual(result['cards'][0]['left']['id'], 'A-invalid')
        self.assertEqual(result['cards'][0]['matched_test_ids'], ['B-invalid'])

    def test_exact_path_not_basename_substring_or_directory(self):
        report = self.report()
        for path in ('missing/' + self.path, 'test_inventory', 'tests'):
            result = card_query.get_ut_cards(report, path)
            self.assertEqual(result['status'], 'NOT_FOUND')
            self.assertEqual(result['cards'], [])
        self.assertEqual(card_query.get_ut_cards(report, './' + self.path.replace('/', '\\'))['status'], 'FOUND')

    def test_absolute_paths_require_explicit_root_and_stay_within_it(self):
        report = self.report()
        for root in ('/workspace/project', 'D:\\workspace\\project'):
            path = root + '/' + self.path
            self.assertEqual(card_query.get_ut_cards(report, path, project_root=root)['status'], 'FOUND')
            with self.assertRaises(ValidationError):
                card_query.get_ut_cards(report, path)
            with self.assertRaises(ValidationError):
                card_query.get_ut_cards(report, path, project_root=root + '-other')
        for path in ('', '../escape.py', 'tests/../escape.py', 'C:relative.py'):
            with self.assertRaises(ValidationError):
                card_query.get_ut_cards(report, path)

    def test_no_candidate_limit_and_children_do_not_add_cards(self):
        view = view_data(self.data)
        base = view['records'][0]
        view['records'], view['pairs'] = [], []
        for i in range(205):
            record = copy.deepcopy(base)
            record.update(id=f'A-{i}', repo='A', path=self.path)
            record['result']['children'] = [{'name': 'child', 'status': 'SKIP'}]
            view['records'].append(record)
            view['pairs'].append({'id': f'pair-{i}', 'a': record['id'], 'b': None})
        report = self.root / 'large.html'
        report.write_text('<script id="ut-data" type="application/json">' + json.dumps(view) + '</script>', encoding='utf-8')
        result = card_query.get_ut_cards(report, self.path)
        self.assertEqual(result['card_count'], 205)
        self.assertEqual(len(result['cards']), 205)
        self.assertFalse(result['truncated'])

    def test_audit_full_and_legacy_quality_and_locator(self):
        for name in ('audit_input.json', 'full_input.json'):
            self.data = load_data(ROOT / 'examples' / name)
            report = self.report()
            path = next(t['path'] for t in self.data['test_cases'] if t['id'] == 'A-invalid')
            result = card_query.get_ut_cards(report, path, project='A')
            card = next(c for c in result['cards'] if c['left']['id'] == 'A-invalid')
            self.assertEqual(card['quality'], card_query.get_ut_card(report, test_id='A-invalid')['card']['quality'])
            if name.startswith('audit'):
                self.assertIsNone(card['right'])
        view = view_data(self.data)
        view['meta'].pop('capabilities')
        report.write_text('<script id="ut-data" type="application/json">' + json.dumps(view) + '</script>', encoding='utf-8')
        self.assertFalse(card_query.get_ut_cards(report, path)['cards'][0]['locator']['supported'])

    def test_cli_file_query_rejects_ignored_options_and_preserves_output(self):
        report = self.report()
        cmd = [sys.executable, str(ROOT / 'scripts/query_report.py'), str(report), '--file', self.path, '--detail']
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), card_query.get_ut_cards(report, self.path))
        for extra in (['--name', 'test_x'], ['--limit', '1'], ['--match', 'contains'], ['--path', self.path]):
            self.assertEqual(subprocess.run(cmd + extra, capture_output=True).returncode, 2)
        output = self.root / 'existing.json'
        output.write_text('preserve')
        self.assertEqual(subprocess.run(cmd + ['--output', str(output)], capture_output=True).returncode, 2)
        self.assertEqual(output.read_text(), 'preserve')
