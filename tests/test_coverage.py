from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

from ut_diff_report.coverage import parse_coverage, percentage


class CoverageTests(unittest.TestCase):
    def test_separate_export_requires_original_hash_bound_data_and_same_source(self):
        from datetime import datetime, timezone
        root_script = Path(__file__).resolve().parents[1] / 'scripts/calculate_coverage.py'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'data.bin'
            data.write_bytes(b'synthetic intermediate')
            exported = root / 'report.info'
            exported.write_text('SF:item.js\nDA:1,1\nend_of_record\n', encoding='utf-8')
            base = {'cwd': str(root), 'command': ['synthetic-test'], 'run_at': datetime.now(timezone.utc).isoformat(),
                    'timeout': False, 'exit_code': 0, 'source_digest_before': 'a' * 64, 'source_digest_after': 'a' * 64}
            test = {**base, 'produced_artifacts': [{'path': str(data), 'sha256': hashlib.sha256(data.read_bytes()).hexdigest()}]}
            export = {**base, 'command': ['synthetic-export', '--data-file=data.bin'],
                'produced_artifacts': [{'path': str(exported), 'sha256': hashlib.sha256(exported.read_bytes()).hexdigest()}]}
            (root / 'test.json').write_text(json.dumps(test), encoding='utf-8')
            (root / 'export.json').write_text(json.dumps(export), encoding='utf-8')
            command = [sys.executable, str(root_script), '--input', str(exported), '--format', 'lcov',
                '--invocation', str(root / 'export.json'), '--test-invocation', str(root / 'test.json'),
                '--data-artifact', str(data), '--project-id', 'A', '--tool', 'synthetic', '--tool-version', '1',
                '--scope', 'UT', '--scope-evidence', 'Synthetic lineage contract fixture', '--output', str(root / 'normalized.json')]
            result = subprocess.run(command, cwd=root_script.parent.parent, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            normalized = json.loads((root / 'normalized.json').read_text(encoding='utf-8'))
            self.assertEqual(normalized['command'], ['synthetic-test'])
            self.assertEqual(normalized['report_command'], export['command'])
            (root / 'normalized.json').unlink()
            data.write_bytes(b'modified')
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('original test invocation', result.stderr)

    def parse(self, fmt, content):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'coverage.dat'
            p.write_text(content, encoding='utf-8')
            return parse_coverage(p, fmt)

    def test_go_statement_denominator_is_not_mislabeled_as_lines(self):
        r = self.parse('go', 'mode: set\nsample/item.go:3.1,5.2 2 1\nsample/item.go:6.1,7.2 1 0\n')
        self.assertEqual(r['metrics']['statement'], {'covered': 2, 'total': 3})
        self.assertNotIn('line', r['metrics'])

    def test_python_line_and_branch_actual_counts(self):
        r = self.parse('coveragepy', '{"files":{"item.py":{"executed_lines":[1,2],"missing_lines":[3],"summary":{"covered_lines":2,"num_statements":3,"covered_branches":1,"num_branches":2}}}}')
        self.assertEqual(r['metrics']['line'], {'covered': 2, 'total': 3})
        self.assertEqual(r['metrics']['branch'], {'covered': 1, 'total': 2})

    def test_lcov_and_cobertura_counts(self):
        lcov = self.parse('lcov', 'SF:item.js\nDA:1,1\nDA:2,0\nBRDA:1,0,0,1\nBRDA:1,0,1,-\nFNDA:1,reserve\nend_of_record\n')
        self.assertEqual(lcov['metrics']['line'], {'covered': 1, 'total': 2})
        self.assertEqual(lcov['metrics']['function'], {'covered': 1, 'total': 1})
        xml = self.parse('cobertura', '<coverage><packages><package><classes><class filename="item.py"><lines><line number="1" hits="1" branch="true" condition-coverage="50% (1/2)"/><line number="2" hits="0"/></lines></class></classes></package></packages></coverage>')
        self.assertEqual(xml['metrics']['branch'], {'covered': 1, 'total': 2})
        self.assertIsNone(percentage({'covered': 0, 'total': 0}))

    def test_impossible_counts_and_unknown_formats_rejected(self):
        with self.assertRaises(ValueError):
            self.parse('coveragepy', '{"files":{"x":{"summary":{"covered_lines":9,"num_statements":1}}}}')
        with self.assertRaises(ValueError):
            self.parse('guess', 'arbitrary data')
