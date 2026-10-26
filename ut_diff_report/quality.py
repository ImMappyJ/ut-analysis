"""Evidence-based requirement accounting and explicit quality-gate evaluation; no semantic inference."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import re

from .core import check_schema, index_unique, load_data, require

ROOT = Path(__file__).resolve().parents[1]
TRACE_STATES = ('SUFFICIENT', 'PARTIAL', 'UNCOVERED', 'UNKNOWN')


def metric_percent(metric):
    return round(100 * metric['covered'] / metric['total'], 6) if metric and metric['total'] else None


def authoritative(requirement, sources):
    return requirement['testability'] == 'testable' and bool(requirement['source_ids']) and all(
        sources[s]['authority'] == 'authoritative' and sources[s]['type'] != 'implementation'
        for s in requirement['source_ids'])


def validate_quality(data):
    q = data.get('quality')
    require(isinstance(q, dict), 'audit/full require structured quality evidence (empty lists are allowed)')
    check_schema(q, load_data(ROOT / 'references/quality.schema.json'))
    projects = {p['id']: p for p in data['projects']}
    modules = {m['id'] for m in data['modules']}
    tests = {t['id']: t for t in data['test_cases']}
    sources = index_unique(q['sources'], 'quality.sources')
    requirements = index_unique(q['requirements'], 'quality.requirements')
    index_unique(q['issues'], 'quality.issues')
    for requirement in requirements.values():
        require(requirement['module_id'] in modules, 'unknown requirement module')
        require(set(requirement['source_ids']) <= set(sources), 'unknown requirement source')
        require(bool(requirement['source_ids']), 'requirements need explicit product-source provenance')
        index_unique(requirement['criteria'], 'requirement criteria')
        applicable = requirement.get('applicable_projects', list(projects))
        require(bool(applicable) and set(applicable) <= set(projects) and len(applicable) == len(set(applicable)),
                'invalid requirement applicability scope')
        if set(applicable) != set(projects):
            require(bool(requirement.get('applicability_evidence')), 'project-specific requirements need explicit scope evidence')
        if requirement['testability'] == 'testable':
            require(bool(requirement['criteria']), 'testable requirement needs explicit acceptance criteria')
    seen = set()
    for trace in q['traces']:
        rid, pid = trace['requirement_id'], trace['project_id']
        require(rid in requirements and pid in projects and (rid, pid) not in seen, 'duplicate/unknown requirement trace')
        seen.add((rid, pid))
        requirement = requirements[rid]
        require(pid in requirement.get('applicable_projects', projects), 'trace targets a project outside requirement scope')
        criteria = {c['id'] for c in requirement['criteria']}
        require(len(trace['test_ids']) == len(set(trace['test_ids'])), 'duplicate trace test references')
        for tid in trace['test_ids']:
            require(tid in tests and tests[tid]['project_id'] == pid and tests[tid]['kind'] == 'unit',
                    'trace must reference actual unit tests in the same project')
        require(set(trace['covered_criteria']) <= criteria, 'trace references unknown acceptance criteria')
        valid_criteria = set()
        for assertion in trace['assertion_evidence']:
            require(assertion['test_id'] in trace['test_ids'], 'assertion evidence must reference a traced UT')
            require(set(assertion['criteria_ids']) <= criteria, 'assertion references unknown criterion')
            if assertion['validity'] == 'valid':
                valid_criteria.update(assertion['criteria_ids'])
        require(set(trace['covered_criteria']) <= valid_criteria, 'covered criteria need effective assertion evidence')
        if trace['status'] == 'SUFFICIENT':
            require(authoritative(requirement, sources), 'cannot establish product sufficiency from implementation/uncertain sources')
            require(bool(trace['test_ids']) and criteria == set(trace['covered_criteria']) and not trace['missing_scenarios'],
                    'SUFFICIENT needs all acceptance criteria and no known missing scenarios')
        if trace['status'] == 'UNCOVERED':
            require(not trace['test_ids'] and not trace['covered_criteria'], 'UNCOVERED conflicts with claimed UT coverage')
        if not authoritative(requirement, sources):
            require(trace['status'] == 'UNKNOWN', 'ambiguous/unreliable requirements cannot be marked verified/uncovered')
    for issue in q['issues']:
        require(issue['project_id'] in projects, 'unknown issue project')
        require(set(issue['requirement_ids']) <= set(requirements), 'unknown issue product target')
        for tid in issue['test_ids']:
            require(tid in tests and tests[tid]['project_id'] == issue['project_id'], 'invalid issue test reference')
        require(not (issue['certainty'] == 'confirmed' and issue['verification'] == 'heuristic'),
                'static heuristic alone cannot confirm invalid tests or product conflicts')
        if issue['type'] == 'conflict' and issue['certainty'] == 'confirmed':
            require(bool(issue['requirement_ids']) and all(authoritative(requirements[r], sources) for r in issue['requirement_ids']),
                    'confirmed product conflict needs authoritative product criteria')
    for pid, tids in q['reviewed_test_ids'].items():
        require(pid in projects and len(tids) == len(set(tids)), 'unknown review project or duplicate review references')
        require(all(t in tests and tests[t]['project_id'] == pid and tests[t]['kind'] == 'unit' for t in tids),
                'reviewed IDs must be actual unit entries')
    seen_coverage = set()
    for coverage in q['coverage']:
        pid = coverage['project_id']
        require(pid in projects and pid not in seen_coverage, 'duplicate/unknown coverage project')
        seen_coverage.add(pid)
        if not coverage['collected']:
            require(bool(coverage.get('reason')), 'uncollected coverage needs a reason')
            require(not coverage.get('metrics'), 'uncollected coverage cannot claim metrics/zero percentages')
            continue
        for field in ('tool', 'tool_version', 'command', 'run_at', 'scope', 'scope_evidence', 'artifact',
                      'denominator', 'exclusions', 'unmeasured_files', 'metrics', 'files'):
            require(field in coverage, 'collected coverage missing provenance: ' + field)
        require(bool(coverage['command']) and bool(coverage['scope_evidence']) and bool(coverage['metrics']),
                'collected coverage needs actual invocation, scope and measured counts')
        try:
            stamp = datetime.fromisoformat(coverage['run_at'].replace('Z', '+00:00'))
            require(stamp.tzinfo is not None, 'coverage time needs timezone')
        except ValueError as exc:
            require(False, 'invalid coverage run_at: ' + str(exc))
        for metrics in [coverage['metrics']] + [f['metrics'] for f in coverage['files']]:
            for metric in metrics.values():
                require(0 <= metric['covered'] <= metric['total'], 'impossible coverage numerator/denominator')
        if coverage['files']:
            from .coverage import aggregate
            require(aggregate(coverage['files']) == coverage['metrics'], 'coverage file/global denominator mismatch')
        if projects[pid].get('git', {}).get('sha'):
            verify_source_context(projects[pid]['git'], coverage.get('source_context'), 'coverage')
    for gate in q['policy'].get('code', []):
        require(0 <= gate['minimum'] <= 100, 'coverage target must be between 0 and 100')
        require(set(gate.get('project_ids', projects)) <= set(projects), 'unknown code gate project')
        if gate.get('module_id'):
            require(gate['module_id'] in modules, 'unknown coverage gate module')
    threshold = q['policy'].get('requirements', {}).get('minimum_sufficient_percent')
    require(threshold is None or 0 <= threshold <= 100, 'invalid requirement coverage target')
    return q


def verify_source_context(selected, observed, label):
    require(isinstance(observed, dict), label + ' needs execution source context for selected Git version')
    require(observed.get('sha') == selected.get('sha'), label + ' commit differs from selected branch snapshot')
    norm = lambda p: str(p).replace('\\', '/').rstrip('/')
    require(norm(observed.get('analysis_root')) == norm(selected.get('analysis_root')),
            label + ' analysis root differs from selected branch worktree')
    for context in (selected, observed):
        require(bool(re.fullmatch('[0-9a-f]{64}', context.get('snapshot_digest') or '')),
                label + ' needs a valid selected/actual source fingerprint')
    require(observed['snapshot_digest'] == selected['snapshot_digest'],
            label + ' source fingerprint differs from selected source snapshot')


def module_metrics(coverage, modules, pid):
    import fnmatch
    result = {}
    for module in modules:
        patterns = module.get('project_scopes', {}).get(pid, [])
        selected = [f for f in coverage.get('files', []) if any(
            fnmatch.fnmatchcase(f['path'], p) or f['path'].startswith(p.rstrip('/') + '/') for p in patterns)]
        if selected:
            result[module['id']] = {}
            for file in selected:
                for key, counts in file['metrics'].items():
                    target = result[module['id']].setdefault(key, {'covered': 0, 'total': 0})
                    target['covered'] += counts['covered']
                    target['total'] += counts['total']
    return result


def evaluate_quality(data):
    q = validate_quality(data)
    sources = {s['id']: s for s in q['sources']}
    requirements = q['requirements']
    traces = {(t['project_id'], t['requirement_id']): t for t in q['traces']}
    outcome = {'projects': {}, 'requirement_ids': [r['id'] for r in requirements]}
    for project in data['projects']:
        pid = project['id']
        applicable = [r for r in requirements if pid in r.get('applicable_projects', [p['id'] for p in data['projects']])]
        eligible = [r for r in applicable if authoritative(r, sources)]
        statuses = {r['id']: traces.get((pid, r['id']), {}).get('status', 'UNKNOWN') for r in applicable}
        counts = Counter(statuses.values())
        coverage = next((c for c in q['coverage'] if c['project_id'] == pid),
                        {'project_id': pid, 'collected': False, 'reason': '未提供覆盖率工具执行与产物证据。'})
        by_module = module_metrics(coverage, data['modules'], pid)
        gates = []
        for i, rule in enumerate(q['policy'].get('code', [])):
            if pid not in rule.get('project_ids', [p['id'] for p in data['projects']]):
                continue
            metrics = by_module.get(rule['module_id'], {}) if rule.get('module_id') else coverage.get('metrics', {})
            metric = metrics.get(rule['metric'])
            measured = metric_percent(metric)
            if not coverage['collected'] or coverage.get('scope') != 'UT' or measured is None:
                status, reason = 'INSUFFICIENT EVIDENCE', '未采集可用纯 UT 指标或该指标没有可统计分母；不按 0% 处理。'
            else:
                status = 'PASS' if measured >= rule['minimum'] else 'FAIL'
                reason = f"实测 {rule['metric']} {measured:g}%；目标 {rule['minimum']:g}%；分母 {metric['total']}。"
            gates.append({'id': 'code-' + str(i), 'layer': 'code', 'status': status,
                          'mandatory': rule['mandatory'], 'reason': reason, 'basis': rule['basis']})
        product_rule = q['policy'].get('requirements')
        product_known = bool(eligible)
        if product_rule:
            status, reasons = 'PASS', []
            unknown, failed = False, False
            if not product_known:
                unknown = True
                reasons.append('没有可靠、可验证的产品需求单元。')
            if product_rule.get('core_must_be_sufficient'):
                core = [r for r in applicable if r['priority'] == 'P0']
                if not core:
                    unknown = True
                    reasons.append('未明确核心需求范围。')
                for r in core:
                    state = statuses[r['id']]
                    if not authoritative(r, sources) or state == 'UNKNOWN':
                        unknown = True
                    elif state != 'SUFFICIENT':
                        failed = True
                    reasons.append(r['id'] + ': ' + state)
            target = product_rule.get('minimum_sufficient_percent')
            if target is not None and eligible:
                sufficient = sum(statuses[r['id']] == 'SUFFICIENT' for r in eligible)
                uncertain = sum(statuses[r['id']] == 'UNKNOWN' for r in eligible)
                lower, upper = 100 * sufficient / len(eligible), 100 * (sufficient + uncertain) / len(eligible)
                if upper < target:
                    failed = True
                elif lower < target:
                    unknown = True
                reasons.append(f'充分覆盖 {sufficient}/{len(eligible)} 个明确需求；未知 {uncertain}；目标 {target:g}%。')
            if not product_rule.get('core_must_be_sufficient') and target is None:
                unknown = True
                reasons.append('尚未配置可判定的产品覆盖条件。')
            status = 'FAIL' if failed else 'INSUFFICIENT EVIDENCE' if unknown else 'PASS'
            gates.append({'id': 'requirements', 'layer': 'requirements', 'status': status,
                          'mandatory': product_rule['mandatory'], 'reason': ' '.join(reasons), 'basis': product_rule['basis']})
        issues = [i for i in q['issues'] if i['project_id'] == pid]
        effectiveness = q['policy'].get('effectiveness')
        if effectiveness:
            high = [i for i in issues if i['severity'] == 'high']
            high_tests = {t['id'] for t in data['test_cases'] if t['project_id'] == pid and t['kind'] == 'unit'
                          and any(m['id'] == t['module_id'] and m.get('priority') == 'P0' for m in data['modules'])}
            reviewed = set(q['reviewed_test_ids'].get(pid, []))
            if effectiveness.get('no_confirmed_high_risk') and any(i['certainty'] == 'confirmed' for i in high):
                status, reason = 'FAIL', '存在有明确证据的高风险测试问题。'
            elif not effectiveness.get('no_confirmed_high_risk') or not high_tests or not high_tests <= reviewed or high:
                status, reason = 'INSUFFICIENT EVIDENCE', '高风险 UT 审查范围不完整或存在待验证风险；无问题记录不等于已经审查通过。'
            elif issues:
                status, reason = 'WARN', '已审查高风险 UT；仍有非阻断质量问题。'
            else:
                status, reason = 'PASS', '明确范围内的高风险 UT 已审查，未发现已证实的阻断问题。'
            gates.append({'id': 'effectiveness', 'layer': 'effectiveness', 'status': status,
                          'mandatory': effectiveness['mandatory'], 'reason': reason, 'basis': effectiveness['basis']})
        mandatory = [g for g in gates if g['mandatory']]
        if any(g['status'] == 'FAIL' for g in mandatory):
            verdict, reason = 'FAIL', '至少一个明确配置的强制门禁未满足。'
        elif not mandatory or not product_known or any(g['status'] == 'INSUFFICIENT EVIDENCE' for g in mandatory):
            verdict, reason = 'INSUFFICIENT EVIDENCE', '缺少可靠产品证据、强制门禁配置或完成判定所需的证据。'
        elif any(g['status'] != 'PASS' for g in gates) or issues or any(s != 'SUFFICIENT' for s in statuses.values()):
            verdict, reason = 'WARN', '强制门禁已满足，仍有非阻断性问题或覆盖缺口。'
        else:
            verdict, reason = 'PASS', '全部适用的强制门禁有证据满足。'
        sufficient = sum(statuses[r['id']] == 'SUFFICIENT' for r in eligible)
        outcome['projects'][pid] = {'verdict': verdict, 'reason': reason,
            'product_alignment': 'INSUFFICIENT EVIDENCE' if not product_known else
                'CONFLICT' if any(i['type'] == 'conflict' and i['certainty'] == 'confirmed' for i in issues) else
                'PARTIAL' if any(s != 'SUFFICIENT' for s in statuses.values()) else 'ALIGNED',
            'requirement_counts': {s: counts[s] for s in TRACE_STATES}, 'requirement_total': len(applicable),
            'applicable_requirement_ids': [r['id'] for r in applicable],
            'verifiable_requirement_total': len(eligible),
            'requirement_coverage_percent': round(100 * sufficient / len(eligible), 6) if eligible else None,
            'coverage': coverage, 'module_metrics': by_module, 'gates': gates,
            'module_requirements': [{'module_id': m['id'], 'counts': {s: sum(
                r['module_id'] == m['id'] and statuses[r['id']] == s for r in applicable) for s in TRACE_STATES}}
                for m in data['modules']], 'issues': issues}
    return outcome
