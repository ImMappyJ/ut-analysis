import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ut_diff_report.core import load_data, validate, validate_html

ROOT = Path(__file__).resolve().parents[1]


class EndToEndTests(unittest.TestCase):
    def test_other_workspace_real_and_unrun(self):
        for unrun in (False, True):
            with self.subTest(unrun=unrun), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory) / 'caller workspace'
                command = [sys.executable, str(ROOT / 'scripts/demo_e2e.py'), '--workspace', str(workspace)]
                if unrun:
                    command += ['--without-owners', '--no-execution']
                proc = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=60)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIsNotNone(proc.stdout)
                self.assertIn('"UT"', proc.stdout)
                summary = validate_html(workspace / 'docs/ut_result.html')
                self.assertEqual(summary['UT'], {'A': 3, 'B': 3})
                self.assertEqual(summary['matching'], {'EXACT': 2, 'PARTIAL': 0, 'A_ONLY': 1, 'B_ONLY': 1})
                expected = 'NOT RUN' if unrun else 'PASS'
                self.assertEqual(summary['results']['A'][expected], 3)
                self.assertEqual(summary['results']['B'][expected], 3)
                data = load_data(workspace / 'docs/ut-diff/synthetic-run/comparison.json')
                validate(data)
                self.assertEqual(len(data['owners']), 0 if unrun else 1)
                if not unrun:
                    self.assertEqual(summary['execution']['SAME'], 2)
