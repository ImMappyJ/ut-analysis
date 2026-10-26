"""Resolve projects and create isolated selected-branch contexts; never checkout in user trees."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
from ut_diff_report.discovery import resolve_project, select_mode
from ut_diff_report.git_context import GitSelectionError, cleanup, prepare

configure_cli()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('auto', 'compare', 'audit', 'full'), default='auto',
                        help='auto: one project uses audit; two projects use compare')
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--project', '--project-a', dest='project_a', required=True)
    parser.add_argument('--branch', '--branch-a', dest='branch_a')
    parser.add_argument('--project-b')
    parser.add_argument('--branch-b')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    contexts = []
    output = args.output if args.output.is_absolute() else args.workspace.resolve() / args.output
    try:
        if output.exists():
            raise FileExistsError('choose a fresh context manifest path')
        mode = select_mode(args.mode, project_b=args.project_b, branch_b=args.branch_b)
        for pid, project, branch in [('A', args.project_a, args.branch_a)] + (
                [('B', args.project_b, args.branch_b)] if args.project_b else []):
            context = prepare(resolve_project(project, args.workspace), pid, branch)
            contexts.append(context)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({'mode': mode, 'projects': contexts}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(output)
    except (OSError, ValueError) as exc:
        for context in contexts:
            try:
                cleanup(context)
            except GitSelectionError as cleanup_error:
                print(str(cleanup_error), file=sys.stderr)
        parser.exit(2, str(exc) + '\n')
