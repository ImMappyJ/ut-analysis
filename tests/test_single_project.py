import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ut_diff_report.discovery import select_mode
from ut_diff_report.core import load_data, validate_html
from ut_diff_report.quality import evaluate_quality
from ut_diff_report.report_context import get_requirements

ROOT = Path(__file__).resolve().parents[1]


class SingleProjectTests(unittest.TestCase):
    def test_auto_and_explicit_modes_preserve_intent(self):
        self.assertEqual(select_mode(), 'audit')
        self.assertEqual(select_mode(project_b='other'), 'compare')
        self.assertEqual(select_mode('full', project_b='other'), 'full')
        for mode in ('compare','full'):
            with self.assertRaises(ValueError):
                select_mode(mode)
        with self.assertRaises(ValueError):
            select_mode('audit',project_b='other')
        with self.assertRaises(ValueError):
            select_mode(branch_b='main')

    def test_prepare_one_non_git_project_without_mode_or_second_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'project').mkdir()
            run = subprocess.run([sys.executable,str(ROOT/'scripts/prepare_projects.py'),
                                  '--workspace',str(root),'--project','project','--output','contexts.json'],
                                 capture_output=True,encoding='utf-8')
            self.assertEqual(run.returncode,0,run.stderr)
            contexts=json.loads((root/'contexts.json').read_text(encoding='utf-8'))
            self.assertEqual(contexts['mode'],'audit')
            self.assertEqual(len(contexts['projects']),1)
            self.assertEqual(Path(contexts['projects'][0]['analysis_root']), (root/'project').resolve())

    def test_explicit_diff_missing_b_never_creates_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            run=subprocess.run([sys.executable,str(ROOT/'scripts/prepare_projects.py'),'--mode','compare',
                                '--workspace',str(root),'--project',str(root),'--output','context.json'],capture_output=True)
            self.assertEqual(run.returncode,2)
            self.assertFalse((root/'context.json').exists())

    def test_real_audit_demo_passes_tests_but_retains_requirement_gaps(self):
        from scripts.demo_e2e import demo
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            report=demo(root,mode='audit')
            validate_html(report)
            data=load_data(root/'docs/ut-diff/synthetic-run/analysis.json')
            self.assertEqual([p['id'] for p in data['projects']],['A'])
            self.assertEqual(data['matches'],[])
            self.assertFalse((root/'projects/green').exists())
            self.assertEqual(len(data['execution_results']),3)
            self.assertEqual({r['status'] for r in data['execution_results']},{'PASS'})
            result=evaluate_quality(data)['projects']['A']
            self.assertEqual(result['requirement_counts'],{'SUFFICIENT':1,'PARTIAL':1,'UNCOVERED':1,'UNKNOWN':0})
            self.assertEqual(result['verdict'],'FAIL')
            self.assertFalse(result['coverage']['collected'])
            req=get_requirements(report,requirement_id='REQ-ALL',detail=True)
            self.assertIn('8',req['requirements']['items'][0]['sources'][0]['excerpt'])
            self.assertEqual(req['requirements']['items'][0]['traces'][0]['test_ids'],[])

    def test_audit_static_demo_keeps_not_run_and_compare_stays_two_projects(self):
        from scripts.demo_e2e import demo
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            demo(root/'audit',execute=False,mode='audit')
            data=load_data(root/'audit/docs/ut-diff/synthetic-run/analysis.json')
            self.assertEqual({r['status'] for r in data['execution_results']},{'NOT RUN'})
            demo(root/'compare',execute=False)
            previous=load_data(root/'compare/docs/ut-diff/synthetic-run/comparison.json')
            self.assertEqual(len(previous['projects']),2)
            self.assertEqual(len(previous['matches']),4)
