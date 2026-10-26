"""Create a fully synthetic repair-progress report in a fresh workspace (no UT execution)."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
from ut_diff_report.core import ROOT, load_data, render
from ut_diff_report.progress import prepare_sync, commit_sync, render_progress_report

configure_cli()


def demo(workspace):
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    if any(workspace.iterdir()):
        raise ValueError('demo requires an empty workspace')
    report = render(load_data(ROOT / 'examples/full_input.json'), workspace=workspace)
    notes = workspace / 'docs/result.md'
    notes.write_text('# Synthetic repair notes\n\n## DEMO-1: Keep validation differences\n'
                     'Synthetic decision: preserve the current assertions. No tests were run.\n\n'
                     '## DEMO-2: Candidate scenario\n'
                     'Synthetic plan: add a boundary scenario later. No test exists yet.\n', encoding='utf-8')
    store = workspace / 'docs/ut-progress'
    plan = prepare_sync(notes, store, report, workspace=workspace)
    batch = {'base_revision': None, 'document_sha256': plan['document_sha256'], 'removed': [], 'sections': []}
    data = load_data(ROOT / 'examples/full_input.json')
    test = next(t for t in data['test_cases'] if t['id'] == 'A-invalid')
    for s in plan['changed']:
        existing = s['key'] == 'DEMO-1'
        item = {'issue_id': s['key'], 'targets': [{'project':'A','path':test['path'],'name':test['name'] if existing else 'test_future_boundary'}],
                'status': 'ACCEPTED_DIFFERENCE' if existing else 'PLANNED', 'change': 'UNCHANGED' if existing else 'UNKNOWN',
                'summary': '保留当前输入验证差异（合成示例）' if existing else '待补充边界场景（合成示例）',
                'reason': '合成文档说明需要保留当前断言。' if existing else '仅为候选目标，尚未创建测试。',
                'next_step': '结合实际产品目标继续分析；本示例没有执行测试。', 'owner': 'Example owner',
                'priority': 'P1', 'reported_at': '2026-01-01', 'quote': s['text'].strip().splitlines()[-1],
                'verification': {'status': 'NOT RUN', 'scope': 'Synthetic demo; no test execution.'}}
        batch['sections'].append({'key': s['key'], 'sha256': s['sha256'], 'items': [item]})
    commit_sync(notes, store, report, batch, workspace=workspace)
    return render_progress_report(report, store, workspace / 'docs/ut_progress_report.html')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(demo(args.workspace))
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')
