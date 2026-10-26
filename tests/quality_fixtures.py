import copy
import json
from pathlib import Path


def audit_data():
    root = Path(__file__).resolve().parents[1]
    d = json.loads((root / 'examples/sample_input.json').read_text(encoding='utf-8'))
    d['schema_version'] = '1.1.0'
    d['report_metadata']['mode'] = 'audit'
    d['projects'] = [p for p in d['projects'] if p['id'] == 'A']
    d['test_cases'] = [t for t in d['test_cases'] if t['project_id'] == 'A']
    d['execution_results'] = [r for r in d['execution_results'] if r['test_id'].startswith('A-')]
    d['matches'] = []
    d['differences'] = []
    d['report_metadata']['findings'] = []
    d['quality'] = {'sources': [], 'requirements': [], 'traces': [], 'issues': [],
                    'coverage': [], 'reviewed_test_ids': {}, 'policy': {}}
    return d


def with_requirements(d):
    d = copy.deepcopy(d)
    d['quality']['sources'] = [{'id': 'product', 'type': 'user', 'reference': 'user:request',
        'authority': 'authoritative', 'excerpt': '预留 3 个库存后从 8 减至 5；拒绝零或负数申请。'}]
    d['quality']['requirements'] = [{'id': 'REQ-01', 'module_id': 'inventory', 'description': '正确预留并拒绝非法数量',
        'priority': 'P0', 'source_ids': ['product'], 'testability': 'testable', 'criteria': [
            {'id': 'valid', 'description': '库存 8 预留 3 后剩余 5', 'category': 'normal'},
            {'id': 'invalid', 'description': '拒绝零和负数数量', 'category': 'boundary'}]}]
    d['quality']['traces'] = [{'requirement_id': 'REQ-01', 'project_id': 'A', 'status': 'PARTIAL',
        'test_ids': ['A-reserve'], 'covered_criteria': ['valid'], 'missing_scenarios': ['缺少负数申请验证'],
        'assertion_evidence': [{'test_id': 'A-reserve', 'path': 'test_inventory.py', 'line': 11,
            'code': 'self.assertEqual(reserve(8, 3), 5)', 'criteria_ids': ['valid'], 'validity': 'valid'}],
        'reason': '正常扣减有断言，完整拒绝非法数量的条件没有覆盖。', 'evidence': ['合成库存断言与需求对照']}]
    return d


def measured_coverage(project='A', covered=95, total=100):
    return {'project_id': project, 'collected': True, 'tool': 'synthetic-test-fixture', 'tool_version': '1',
        'command': ['synthetic-runner', '--coverage'], 'run_at': '2026-01-01T00:00:00Z',
        'scope': 'UT', 'scope_evidence': ['Synthetic unit-test-only fixture, not a real project measurement.'],
        'artifact': {'path': 'synthetic.coverage', 'sha256': 'a' * 64},
        'denominator': 'Synthetic executable-line counts for evaluator unit testing only.',
        'exclusions': [], 'unmeasured_files': [], 'metrics': {'line': {'covered': covered, 'total': total}}, 'files': []}
