"""Run ONLY bundled synthetic projects; fixed fixture decisions are not a semantic matcher."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report.core import render, validate
from ut_diff_report.discovery import scan_python
from ut_diff_report.execution import run_unittest
from ut_diff_report.git_context import inspect

ROOT = Path(__file__).resolve().parents[1]


def demo(workspace, owners=True, execute=True, mode='compare'):
    if mode not in ('compare', 'audit'):
        raise ValueError('demo supports compare or audit')
    workspace = Path(workspace).resolve()
    if workspace.exists() and any(workspace.iterdir()):
        raise FileExistsError('demo workspace must be new or empty')
    workspace.mkdir(parents=True, exist_ok=True)
    evidence = workspace / 'docs/ut-diff/synthetic-run'
    evidence.mkdir(parents=True)
    data = {'schema_version': '1.0.0', 'report_metadata': {
        'title': 'Blue × Green · 合成项目实际执行演示', 'run_id': 'synthetic-run',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'counting_policy': '每个顶层 unittest 方法计一次；subTest 作为实际子实例，不增加入口总数。',
        'limitations': ['只分析仓库内合成项目，不代表任何真实业务仓库。',
                        '列表常量比较无法证明目录行为；字符串转换无法证明完整订单流程。'],
        'findings': [{'title': '异名对应与单侧目标', 'description':
                      '两侧库存扣减与拒绝非法数量目标相同；空列表比较和大写转换为单侧局部目标。'}]},
        'projects': [], 'modules': [
            {'id': 'inventory', 'name': '库存预留', 'priority': 'P0', 'priority_reason': '防止无效预留和库存超分配。',
             'owner_ids': ['alpha'] if owners else [], 'mapping_evidence': ['两个夹具均调用 reserve 并断言剩余库存或拒绝非法数量。']},
            {'id': 'auxiliary', 'name': '局部辅助行为', 'priority': 'P1', 'owner_ids': [],
             'priority_reason': '仅常量比较和字符串转换。', 'mapping_evidence': ['源代码只能确认局部断言。']}],
        'owners': [{'id': 'alpha', 'name': '示例负责人甲'}] if owners else [],
        'test_cases': [], 'matches': [], 'execution_results': [], 'differences': []}
    by_project = {}
    for pid, folder in ((('A', 'blue'),) if mode == 'audit' else (('A', 'blue'), ('B', 'green'))):
        project = workspace / 'projects' / folder
        shutil.copytree(ROOT / 'tests/fixtures' / folder, project, ignore=shutil.ignore_patterns('__pycache__'))
        inventory = scan_python(project, pid)
        (evidence / (pid + '-inventory.json')).write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
        data['projects'].append({'id': pid, 'name': folder.title() + ' Sample', 'languages': ['Python'],
                                 'git': {**inspect(project), 'selection': 'working_tree'},
                                 'frameworks': ['unittest'], 'test_file_count': len(inventory['files']),
                                 'scan': {'files': inventory['files'], 'errors': inventory['errors']}})
        result = run_unittest(project, evidence / (pid + '-run')) if execute else None
        by_project[pid] = {}
        for t in inventory['tests']:
            short = t['name'].split('.')[-1]
            is_invalid = short == 'test_reject_invalid'
            is_reserve = short in ('test_reserve_valid', 'test_allocate_units')
            group = 'invalid' if is_invalid else 'reserve' if is_reserve else 'single'
            goal = ('在库存为 8 时，分别预留 0、-1、9 个单位，确认全部抛出 ValueError 并拒绝申请。' if is_invalid else
                    '在库存为 8、申请 3 个单位时，确认预留后剩余库存为 5。' if is_reserve else
                    '比较两个空列表相等；未调用目录业务，不能证明目录查询结果。' if pid == 'A' else
                    '将字符串 packed 转为大写时，确认得到 PACKED；只验证局部转换。')
            data['test_cases'].append({'id': t['id'], 'project_id': pid,
                'module_id': 'inventory' if group != 'single' else 'auxiliary', 'name': t['name'],
                'path': t['path'], 'line': t['line'], 'end_line': t['end_line'], 'suite': t['suite'],
                'kind': 'unit', 'goal': goal, 'evidence': [t['path'] + ':' + str(t['line']) + ' ' + t['code']],
                'code': t['code'], 'assertions': t['assertions'], 'subtests': t['subtests'],
                'scenarios': [goal], 'expectations': [a['code'] for a in t['assertions']]})
            by_project[pid][group] = t['id']
            observed = next((r for r in result['tests'] if r['name'].endswith('.' + t['name'])), None) if result else None
            if observed:
                children = []
                for c in observed['children']:
                    # These fixed semantic keys apply only to the inspected synthetic fixture.
                    key = next(('quantity-' + v for v in ('0', '-1', '9') if '(quantity=' + v + ')' in c['name']), None)
                    children.append({**c, **({'scenario_key': key} if key else {})})
                data['execution_results'].append({'test_id': t['id'], 'status': observed['status'],
                    'command': result['command'], 'run_at': result['run_at'], 'environment': result['environment'],
                    'elapsed_seconds': observed['elapsed_seconds'], 'stdout': observed['output'],
                    'exit_code': result['exit_code'], 'children': children, 'cached': False,
                    'source_digest': result['source_digest_before'],
                    'evidence': ['docs/ut-diff/synthetic-run/' + pid + '-run/unittest.json',
                                 'docs/ut-diff/synthetic-run/' + pid + '-run/invocation.json'],
                    'source_context': result['source_context']})
            else:
                data['execution_results'].append({'test_id': t['id'], 'status': 'NOT RUN',
                    'reason': '演示显式禁用执行，用于验证未运行展示。' if not execute else '原生 runner 没有该入口的运行事件。'})
    for group in (('reserve', 'invalid') if mode == 'compare' else ()):
        data['matches'].append({'id': 'm-' + group, 'a': by_project['A'][group], 'b': by_project['B'][group],
                                'status': 'EXACT', 'evidence': [
                                    '源码的输入和期望相同：库存 8、预留 3 后剩余 5。' if group == 'reserve' else
                                    '两侧均对 0、-1、9 预留数量断言 ValueError；循环与异常断言一致。']})
    for pid in (('A', 'B') if mode == 'compare' else ()):
        data['matches'].append({'id': 'm-only-' + pid, 'a': by_project[pid]['single'] if pid == 'A' else None,
            'b': by_project[pid]['single'] if pid == 'B' else None, 'status': pid + '_ONLY',
            'evidence': ['另一侧未发现相同的局部断言目标；不据此推断缺少业务实现。']})
    if mode == 'audit':
        data['schema_version'] = '1.1.0'
        data['report_metadata'].update(mode='audit', title='单项目 · 按需求分析 UT（合成实跑）',
            findings=[{'title':'现有 UT 全通过仍有需求缺口', 'description':'小数输入缺少拒绝断言，全部库存预留缺少直接测试；实际状态以运行记录为准。'}])
        data['report_metadata']['limitations'] = ['仅运行一个合成项目；需求来自随夹具提供的验收文档。',
            '覆盖率工具未运行；需求覆盖判断与实际测试结果分别记录。']
        data['quality'] = audit_quality(data, workspace, by_project['A'])
    summary = validate(data)
    (evidence / ('analysis.json' if mode == 'audit' else 'comparison.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    output = render(data, workspace=workspace)
    print(json.dumps(summary, ensure_ascii=False))
    return output


def audit_quality(data, workspace, identities):
    """Fixed, reviewed mapping for the bundled acceptance document, not semantic inference."""
    tests = {t['id']:t for t in data['test_cases']}
    source = workspace/'projects/blue/acceptance.md'
    reserve, invalid, auxiliary = (tests[identities[k]] for k in ('reserve','invalid','single'))
    requirements = [
        ('REQ-RESERVE','库存 8 预留 3 后剩余 5',[('remaining','预留 3 个单位返回 5','normal')]),
        ('REQ-INVALID','拒绝非正数、超库存及小数预留数量',
         [('integer-invalid','0、-1、9 均抛出 ValueError','boundary'),('fraction','0.5 抛出 ValueError','boundary')]),
        ('REQ-ALL','允许一次预留全部库存',[('all','库存 8 预留 8 后剩余 0','boundary')])]
    q = {'sources':[{'id':'acceptance','type':'prd','authority':'authoritative',
                     'reference':'projects/blue/acceptance.md','excerpt':source.read_text(encoding='utf-8')}],
         'requirements':[{'id':rid,'description':desc,'module_id':'inventory','priority':'P0',
                          'source_ids':['acceptance'],'testability':'testable',
                          'criteria':[{'id':cid,'description':text,'category':cat} for cid,text,cat in criteria]}
                         for rid,desc,criteria in requirements],
         'traces':[], 'issues':[], 'reviewed_test_ids':{'A':list(tests)},
         'coverage':[{'project_id':'A','collected':False,'reason':'演示未运行覆盖率工具；不以测试数量估算。'}],
         'policy':{'requirements':{'core_must_be_sufficient':True,'mandatory':True,
                                   'basis':'合成验收文档明确要求所有列出的 P0 需求充分覆盖。'}}}
    for rid, test, covered, missing in [
        ('REQ-RESERVE',reserve,['remaining'],[]),
        ('REQ-INVALID',invalid,['integer-invalid'],['缺少 quantity=0.5 拒绝断言']),
        ('REQ-ALL',None,[],['缺少 stock=8、quantity=8、返回 0 的直接测试'])]:
        q['traces'].append({'requirement_id':rid,'project_id':'A',
            'status':'UNCOVERED' if test is None else 'PARTIAL' if missing else 'SUFFICIENT',
            'test_ids':[test['id']] if test else [],'covered_criteria':covered,'missing_scenarios':missing,
            'assertion_evidence':[{'test_id':test['id'],'path':test['path'],'line':test['line'],
                                   'code':test['code'],'criteria_ids':covered,'validity':'valid'}] if test else [],
            'reason':'基于合成验收文档与完整夹具断言核对；运行通过不替代尚未验证的条件。',
            'evidence':['projects/blue/acceptance.md','test_inventory.py 三个 UT 的完整源代码']})
    q['issues'].append({'id':'Q-CONSTANT','project_id':'A','test_ids':[auxiliary['id']],
        'requirement_ids':[],'type':'weak_assertion','severity':'medium','certainty':'suspected',
        'verification':'heuristic','description':'空列表常量比较未调用业务入口。',
        'evidence':[auxiliary['path']+':'+str(auxiliary['line'])+' '+auxiliary['code']],
        'recommendation':'确认该测试原始目标，再建立调用业务入口的断言；不根据名称虚构目录需求。'})
    return q


if __name__ == '__main__':
    from ut_diff_report import configure_cli
    configure_cli()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--without-owners', action='store_true')
    parser.add_argument('--no-execution', action='store_true')
    parser.add_argument('--mode', choices=('compare','audit'), default='compare')
    args = parser.parse_args()
    print(demo(args.workspace, not args.without_owners, not args.no_execution, args.mode))
