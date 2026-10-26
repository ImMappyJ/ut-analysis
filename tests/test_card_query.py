import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ut_diff_report.core import load_data, render, ValidationError
from ut_diff_report.card_query import get_ut_card

ROOT = Path(__file__).resolve().parents[1]


class CardQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = load_data(ROOT / 'examples/sample_input.json')

    def tearDown(self):
        self.temp.cleanup()

    def report(self, data=None):
        return render(data or self.data, workspace=self.root, replace=True)

    def test_same_diff_row_is_one_card_with_both_sides_and_original_evidence(self):
        report = self.report()
        before = hashlib.sha256(report.read_bytes()).hexdigest()
        result = get_ut_card(report, 'test_reject_invalid')
        self.assertEqual(result['status'], 'FOUND')
        self.assertEqual(result['candidate_count'], 1)
        card = result['card']
        self.assertEqual(card['relation']['match'], 'PARTIAL')
        self.assertEqual(len(card['matched_test_ids']), 2)
        self.assertEqual(card['left']['result']['status'], 'NOT RUN')
        self.assertIn('ValueError', card['right']['code'])
        self.assertEqual(result['source']['sha256'], before)
        self.assertEqual(hashlib.sha256(report.read_bytes()).hexdigest(), before)

    def test_ambiguous_names_need_project_path_or_id_instead_of_first_match(self):
        duplicate = copy.deepcopy(self.data['test_cases'][0])
        duplicate.update(id='A-duplicate', path='other/test_inventory.py')
        self.data['test_cases'].append(duplicate)
        self.data['matches'].append({'id': 'duplicate', 'a': duplicate['id'], 'b': None,
                                    'status': 'A_ONLY', 'evidence': ['Synthetic separate path.']})
        report = self.report()
        result = get_ut_card(report, duplicate['name'])
        self.assertEqual(result['status'], 'AMBIGUOUS')
        self.assertEqual(result['candidate_count'], 2)
        self.assertNotIn('card', result)
        chosen = get_ut_card(report, duplicate['name'], project='A', path=duplicate['path'])
        self.assertEqual(chosen['card']['left']['id'], duplicate['id'])
        self.assertIsNone(chosen['card']['right'])
        self.assertEqual(get_ut_card(report, test_id=duplicate['id'])['status'], 'FOUND')

    def test_not_found_never_falls_back_to_a_similar_name(self):
        report = self.report()
        self.assertEqual(get_ut_card(report, 'reserve')['status'], 'NOT_FOUND')
        self.assertEqual(get_ut_card(report, 'reserve', match='contains')['status'], 'FOUND')
        self.assertEqual(get_ut_card(report, 'test_reserve_valid', project='B')['status'], 'NOT_FOUND')

    def test_audit_returns_single_side_and_full_attaches_relevant_quality_evidence(self):
        report = self.report(load_data(ROOT / 'examples/audit_input.json'))
        card = get_ut_card(report, 'test_catalog_empty')['card']
        self.assertEqual(card['kind'], 'audit')
        self.assertIsNone(card['right'])
        self.assertTrue(card['quality']['issues'])
        report = self.report(load_data(ROOT / 'examples/full_input.json'))
        card = get_ut_card(report, 'test_reject_invalid')['card']
        self.assertEqual({r['id'] for r in card['quality']['requirements']}, {'REQ-INVALID'})
        self.assertEqual(len(card['quality']['traces']), 2)

    def test_qualified_name_and_runtime_child_return_parent_card_once(self):
        from ut_diff_report.core import view_data
        view = view_data(self.data)
        record = next(r for r in view['records'] if r['name'] == 'test_catalog_empty')
        record['name'] = 'CatalogTests.test_catalog_empty'
        record['result']['children'] = [{'name': 'CatalogTests.test_catalog_empty (value=0)', 'status': 'SKIP'}]
        report = self.root / 'synthetic.html'
        report.write_text('<script id="ut-data" type="application/json">' + json.dumps(view) + '</script>', encoding='utf-8')
        self.assertEqual(get_ut_card(report, 'test_catalog_empty')['status'], 'FOUND')
        result = get_ut_card(report, 'CatalogTests.test_catalog_empty (value=0)')
        self.assertEqual(result['card']['matched_instances'][0]['name'], 'CatalogTests.test_catalog_empty (value=0)')
        self.assertEqual(result['card']['left']['id'], record['id'])

    def test_unknown_format_and_duplicate_record_ids_are_rejected_without_execution(self):
        report = self.root / 'unknown.html'
        report.write_text('<script>throw new Error("must never execute")</script>', encoding='utf-8')
        with self.assertRaises(ValidationError):
            get_ut_card(report, 'anything')
        from ut_diff_report.core import view_data
        view = view_data(self.data)
        view['records'].append(view['records'][0])
        report.write_text('<script id="ut-data" type="application/json">' + json.dumps(view) + '</script>', encoding='utf-8')
        with self.assertRaises(ValidationError):
            get_ut_card(report, 'anything')

    def test_current_report_has_card_deep_link_capability(self):
        result = get_ut_card(self.report(), 'test_reserve_valid')
        locator = result['candidates'][0]['locator']
        self.assertTrue(locator['supported'])
        self.assertIn('#ut-card=A-reserve', locator['url'])

    def test_old_report_without_deep_link_is_readable_without_modification(self):
        from ut_diff_report.core import view_data
        view = view_data(self.data)
        view['meta'].pop('capabilities')
        view['meta']['templateVersion'] = '1.1.0'
        report = self.root / 'legacy.html'
        report.write_text('<script id="ut-data" type="application/json">' + json.dumps(view) + '</script>', encoding='utf-8')
        result = get_ut_card(report, 'test_reserve_valid')
        self.assertEqual(result['status'], 'FOUND')
        self.assertFalse(result['candidates'][0]['locator']['supported'])
        self.assertIsNone(result['candidates'][0]['locator']['url'])

    def test_candidate_limit_does_not_turn_multiple_matches_into_one_card(self):
        result = get_ut_card(self.report(), 'test_', match='contains', limit=1)
        self.assertEqual(result['status'], 'AMBIGUOUS')
        self.assertEqual(result['candidate_count'], 4)
        self.assertEqual(len(result['candidates']), 1)
        self.assertTrue(result['truncated'])
        self.assertNotIn('card', result)

    def test_cli_is_json_and_preserves_existing_output(self):
        report = self.report()
        script = ROOT / 'scripts/query_report.py'
        command = [sys.executable, str(script), str(report), '--name', 'test_reject_invalid']
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'FOUND')
        output = self.root / 'existing.json'
        output.write_text('preserve', encoding='utf-8')
        result = subprocess.run(command + ['--output', str(output)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output.read_text(), 'preserve')
