import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ut_diff_report.core import comparison
from ut_diff_report.execution import import_junit, parse_go_json, run_unittest


class ExecutionTests(unittest.TestCase):
    def test_explicit_unittest_selection_excludes_unselected_integration_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / 'project'
            project.mkdir()
            (project / 'test_scope.py').write_text('import unittest\nclass Tests(unittest.TestCase):\n'
                '    def test_unit(self): self.assertEqual(2 + 3, 5)\n'
                '    def test_integration(self): self.fail("must not be selected")\n', encoding='utf-8')
            result = run_unittest(project, root / 'evidence', test_ids=['test_scope.Tests.test_unit'])
            self.assertEqual(result['exit_code'], 0)
            self.assertEqual([r['name'] for r in result['tests']], ['test_scope.Tests.test_unit'])

    def test_class_setup_error_is_retained_without_inventing_test_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'test_setup.py').write_text('''import unittest
class TestSetup(unittest.TestCase):
    @classmethod
    def setUpClass(cls): raise RuntimeError("synthetic setup unavailable")
    def test_unstarted(self): self.fail("never called")
''', encoding='utf-8')
            result = run_unittest(root, root / 'evidence')
            self.assertEqual(result['exit_code'], 1)
            self.assertEqual(result['tests'], [])
            self.assertIn('synthetic setup unavailable', result['lifecycle_events'][0]['output'])

    def test_framework_outcomes_and_subtest_failure(self):
        code = '''import unittest
class TestOutcomes(unittest.TestCase):
    def test_fail(self): self.assertEqual(1, 2)
    def test_error(self): raise RuntimeError("synthetic error")
    @unittest.skip("synthetic skip")
    def test_skip(self): pass
    def test_sub(self):
        for value in (1, 2):
            with self.subTest(value=value): self.assertEqual(value, 1)
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'test_outcomes.py').write_text(code, encoding='utf-8')
            results = run_unittest(root, root / 'evidence')['tests']
            by_name = {r['name'].split('.')[-1]: r for r in results}
            self.assertEqual({k: v['status'] for k, v in by_name.items()},
                             {'test_fail': 'FAIL', 'test_error': 'ERROR', 'test_skip': 'SKIP', 'test_sub': 'FAIL'})
            self.assertEqual([c['status'] for c in by_name['test_sub']['children']], ['PASS', 'FAIL'])

    def test_unmapped_children_do_not_imply_semantic_equality(self):
        a = {'status': 'PASS', 'children': [{'name': 'same_name', 'status': 'PASS'}]}
        self.assertEqual(comparison(a, a), 'UNKNOWN')
        a['children'][0]['scenario_key'] = 'zero-quantity'
        self.assertEqual(comparison(a, a), 'SAME')
        b = {'status': 'PASS', 'children': [{'scenario_key': 'negative-quantity', 'status': 'PASS'}]}
        self.assertEqual(comparison(a, b), 'DIFFERENT')

    def test_go_native_events_no_invented_unobserved_passes(self):
        events = [{'Package': 'sample', 'Test': 'TestReserve', 'Action': 'run'},
                  {'Package': 'sample', 'Test': 'TestReserve/zero', 'Action': 'skip'},
                  {'Package': 'sample', 'Test': 'TestReserve', 'Action': 'pass', 'Elapsed': .01}]
        results = parse_go_json('\n'.join(json.dumps(e) for e in events))
        self.assertEqual(len(results['tests']), 1)
        self.assertEqual(results['tests'][0]['children'][0]['status'], 'SKIP')

    def test_junit_retains_instances_and_rejects_entities(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'test.xml'
            p.write_text('<testsuite><testcase name="zero" time="0.1"/><testcase name="negative"><failure message="expected rejection"/></testcase></testsuite>', encoding='utf-8')
            results = import_junit(p)
            self.assertEqual([r['status'] for r in results['tests']], ['PASS', 'FAIL'])
            p.write_text('<!DOCTYPE x [<!ENTITY demo "bad">]><testsuite/>', encoding='utf-8')
            with self.assertRaises(ValueError):
                import_junit(p)

    def test_cli_rejects_stale_junit_before_running_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'old.xml').write_text('<testsuite/>', encoding='utf-8')
            sentinel = root / 'must-not-exist'
            script = Path(__file__).resolve().parents[1] / 'scripts/run_tests.py'
            process = subprocess.run([sys.executable, str(script), '--project', str(root),
                '--artifacts', str(root / 'evidence'), '--framework', 'command', '--junit', 'old.xml', '--',
                sys.executable, '-c', 'from pathlib import Path; Path("must-not-exist").touch()'],
                capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(process.returncode, 2)
            self.assertIn('already exists', process.stderr)
            self.assertFalse(sentinel.exists())


if __name__ == '__main__':
    unittest.main()
