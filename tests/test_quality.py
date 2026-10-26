import copy
from pathlib import Path
import tempfile
import unittest

from quality_fixtures import audit_data, measured_coverage, with_requirements
from ut_diff_report.core import ValidationError, render, validate, validate_html
from ut_diff_report.quality import evaluate_quality, verify_source_context


class QualityTests(unittest.TestCase):
    def test_same_commit_and_directory_require_identical_source_fingerprint(self):
        selected = {'sha': 'a' * 40, 'analysis_root': '/synthetic/project', 'snapshot_digest': 'b' * 64}
        verify_source_context(selected, dict(selected), 'test execution')
        for fingerprint in ('c' * 64, 'not-a-hash', None):
            with self.assertRaises(ValidationError):
                verify_source_context(selected, {**selected, 'snapshot_digest': fingerprint}, 'test execution')

    def test_audit_accepts_one_project_and_missing_product_is_not_pass(self):
        d = audit_data()
        validate(d)
        result = evaluate_quality(d)['projects']['A']
        self.assertEqual(result['verdict'], 'INSUFFICIENT EVIDENCE')
        self.assertIsNone(result['requirement_coverage_percent'])
        self.assertFalse(result['coverage']['collected'])
        with tempfile.TemporaryDirectory() as directory:
            p = render(d, workspace=Path(directory))
            validate_html(p)

    def test_high_code_coverage_does_not_override_missing_core_behavior(self):
        d = with_requirements(audit_data())
        d['quality']['coverage'] = [measured_coverage()]
        d['quality']['policy'] = {'code': [{'metric': 'line', 'minimum': 85, 'mandatory': True,
            'basis': 'user target'}], 'requirements': {'core_must_be_sufficient': True, 'mandatory': True,
            'basis': 'user acceptance criteria'}}
        result = evaluate_quality(d)['projects']['A']
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual(result['gates'][0]['status'], 'PASS')
        self.assertEqual(result['requirement_counts']['PARTIAL'], 1)

    def test_uncollected_is_not_zero_and_mixed_is_not_ut(self):
        d = with_requirements(audit_data())
        d['quality']['policy'] = {'code': [{'metric': 'line', 'minimum': 85, 'mandatory': True, 'basis': 'user target'}]}
        self.assertEqual(evaluate_quality(d)['projects']['A']['gates'][0]['status'], 'INSUFFICIENT EVIDENCE')
        d['quality']['coverage'] = [{**measured_coverage(), 'scope': 'MIXED'}]
        self.assertEqual(evaluate_quality(d)['projects']['A']['gates'][0]['status'], 'INSUFFICIENT EVIDENCE')

    def test_no_policy_cannot_become_formal_pass(self):
        d = with_requirements(audit_data())
        d['quality']['coverage'] = [measured_coverage()]
        self.assertEqual(evaluate_quality(d)['projects']['A']['verdict'], 'INSUFFICIENT EVIDENCE')

    def test_sufficient_requires_assertions_for_every_criterion(self):
        d = with_requirements(audit_data())
        d['quality']['traces'][0]['status'] = 'SUFFICIENT'
        with self.assertRaises(ValidationError):
            evaluate_quality(d)

    def test_complete_evidence_and_explicit_gate_can_pass(self):
        d = with_requirements(audit_data())
        req = d['quality']['requirements'][0]
        req['criteria'] = req['criteria'][:1]
        trace = d['quality']['traces'][0]
        trace.update(status='SUFFICIENT', missing_scenarios=[])
        d['quality']['policy'] = {'requirements': {'core_must_be_sufficient': True,
            'mandatory': True, 'basis': 'user acceptance criteria'}}
        r = evaluate_quality(d)['projects']['A']
        self.assertEqual(r['verdict'], 'PASS')
        self.assertEqual(r['requirement_coverage_percent'], 100)

    def test_heuristic_cannot_be_a_confirmed_invalid_test(self):
        d = audit_data()
        d['quality']['issues'] = [{'id': 'q1', 'project_id': 'A', 'test_ids': ['A-catalog'],
            'requirement_ids': [], 'type': 'weak_assertion', 'severity': 'high', 'certainty': 'confirmed',
            'verification': 'heuristic', 'description': '可能未验证实际目录行为', 'evidence': ['常量列表比较'],
            'recommendation': '对实际目录查询结果建立断言。'}]
        with self.assertRaises(ValidationError):
            evaluate_quality(d)

    def test_full_mode_keeps_existing_diff_and_normalized_requirement_ids(self):
        d = with_requirements(audit_data())
        # Reuse the public synthetic comparison document as the two-project baseline.
        import json
        root = Path(__file__).resolve().parents[1]
        full = json.loads((root / 'examples/sample_input.json').read_text(encoding='utf-8'))
        full.update(schema_version='1.1.0', quality=copy.deepcopy(d['quality']))
        full['report_metadata']['mode'] = 'full'
        result = evaluate_quality(full)
        self.assertEqual(set(result['projects']), {'A', 'B'})
        self.assertEqual(result['projects']['B']['requirement_counts']['UNKNOWN'], 1)
        with tempfile.TemporaryDirectory() as directory:
            out = render(full, workspace=Path(directory))
            summary = validate_html(out)
            self.assertEqual(summary['matching']['PARTIAL'], 1)

    def test_requirement_percent_uses_units_and_unknown_bounds(self):
        d = with_requirements(audit_data())
        d['quality']['policy'] = {'requirements': {'minimum_sufficient_percent': 100,
            'mandatory': True, 'basis': 'user target'}}
        # Adding many UT references cannot increase the number of verified requirement units.
        d['quality']['traces'][0]['test_ids'].append('A-invalid')
        self.assertEqual(evaluate_quality(d)['projects']['A']['requirement_coverage_percent'], 0)
        d['quality']['traces'] = []
        self.assertEqual(evaluate_quality(d)['projects']['A']['verdict'], 'INSUFFICIENT EVIDENCE')

    def test_implementation_is_not_an_authoritative_product_source(self):
        d = with_requirements(audit_data())
        d['quality']['sources'][0].update(type='implementation', authority='supporting')
        d['quality']['traces'][0].update(status='UNKNOWN')
        r = evaluate_quality(d)['projects']['A']
        self.assertEqual(r['verdict'], 'INSUFFICIENT EVIDENCE')
        self.assertIsNone(r['requirement_coverage_percent'])

    def test_branch_coverage_context_cannot_reference_another_commit(self):
        d = with_requirements(audit_data())
        d['projects'][0]['git'] = {'sha': 'a' * 40, 'analysis_root': '/synthetic/selected'}
        c = measured_coverage()
        c['source_context'] = {'sha': 'b' * 40, 'analysis_root': '/synthetic/selected', 'snapshot_digest': 'c' * 64}
        d['quality']['coverage'] = [c]
        with self.assertRaises(ValidationError):
            evaluate_quality(d)

    def test_project_specific_product_scope_is_not_a_missing_requirement_in_other_project(self):
        d = with_requirements(audit_data())
        d['projects'].append({'id': 'B', 'name': 'Synthetic other product'})
        d['quality']['requirements'][0].update(applicable_projects=['A'],
            applicability_evidence=['Synthetic user explicitly scopes this product rule to A only.'])
        d['quality']['policy'] = {'requirements': {'core_must_be_sufficient': True,
            'mandatory': True, 'basis': 'user target'}}
        result = evaluate_quality(d)
        self.assertEqual(result['projects']['A']['verdict'], 'FAIL')
        self.assertEqual(result['projects']['B']['requirement_total'], 0)
        self.assertEqual(result['projects']['B']['requirement_counts']['UNCOVERED'], 0)
        d['quality']['requirements'][0]['applicability_evidence'] = []
        with self.assertRaises(ValidationError):
            evaluate_quality(d)
