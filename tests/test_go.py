import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from ut_diff_report.execution import capture, parse_go_json

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('go'), 'Go toolchain not installed')
class GoTests(unittest.TestCase):
    def test_actual_coverage_artifact_is_bound_to_invocation_and_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / 'project'
            shutil.copytree(ROOT / 'tests/fixtures/go', project)
            profile, normalized = root / 'coverage.out', root / 'normalized.json'
            command = [sys.executable, str(ROOT / 'scripts/run_tests.py'), '--project', str(project),
                '--artifacts', str(root / 'evidence'), '--framework', 'go', '--fresh-output', str(profile), '--',
                'go', 'test', '-json', '-count=1', '-coverprofile=' + str(profile), './...']
            run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr)
            normalize = subprocess.run([sys.executable, str(ROOT / 'scripts/calculate_coverage.py'),
                '--input', str(profile), '--format', 'go', '--invocation', str(root / 'evidence/invocation.json'),
                '--project-id', 'A', '--tool', 'go test', '--tool-version', subprocess.check_output(['go', 'version']).decode().strip(),
                '--scope', 'UT', '--scope-evidence', 'Only the synthetic TestReserve entry; benchmark not selected.',
                '--strip-prefix', 'sample.invalid/inventory', '--output', str(normalized)],
                capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(normalize.returncode, 0, normalize.stderr)
            measured = json.loads(normalized.read_text(encoding='utf-8'))
            self.assertTrue(measured['collected'])
            self.assertNotIn('line', measured['metrics'])
            self.assertGreater(measured['metrics']['statement']['covered'], 0)
            self.assertGreater(measured['metrics']['statement']['total'], measured['metrics']['statement']['covered'])
            self.assertEqual(measured['files'][0]['path'], 'inventory.go')
            self.assertEqual(len(measured['artifact']['sha256']), 64)

    def test_go_ast_and_native_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / 'project'
            shutil.copytree(ROOT / 'tests/fixtures/go', project)
            output = root / 'inventory.json'
            subprocess.run(['go', 'run', str(ROOT / 'scripts/scan_go.go'), str(project), 'A', str(output)],
                           check=True, capture_output=True, timeout=60)
            inventory = json.loads(output.read_text(encoding='utf-8'))
            self.assertFalse(inventory['errors'])
            decls = inventory['files'][0]['decls']
            self.assertEqual({d['kind'] for d in decls}, {'test', 'benchmark'})
            test = next(d for d in decls if d['kind'] == 'test')
            self.assertEqual(len(test['runs']), 1)
            execution = capture(['go', 'test', '-json', '-count=1', './...'], project, root / 'evidence', timeout=60)
            observed = parse_go_json(execution['stdout'])
            self.assertEqual(execution['exit_code'], 0, execution['stderr'])
            self.assertEqual(observed['tests'][0]['status'], 'PASS')
            self.assertEqual(observed['tests'][0]['children'][0]['status'], 'PASS')
