"""Prepare changed Markdown sections, commit Agent annotations, or render a progress report."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
from ut_diff_report.progress import prepare_sync, commit_sync, render_progress_report, _json

configure_cli()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'commit', 'render'))
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--notes', type=Path, default=Path('docs/result.md'))
    parser.add_argument('--store', type=Path, default=Path('docs/ut-progress'))
    parser.add_argument('--report', type=Path, default=Path('docs/ut_result.html'))
    parser.add_argument('--annotations', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--replace', action='store_true')
    parser.add_argument('--refresh-section', action='append', default=[], help='explicitly re-analyze an unchanged task key (prepare only)')
    args = parser.parse_args()
    resolve = lambda p: p if p.is_absolute() else args.workspace / p
    try:
        if args.action == 'prepare':
            result = prepare_sync(resolve(args.notes), resolve(args.store), resolve(args.report), workspace=args.workspace, refresh_sections=args.refresh_section)
        elif args.action == 'commit':
            if args.refresh_section:
                parser.error('commit takes refresh_sections and correction_reason from annotations')
            if not args.annotations:
                parser.error('commit requires --annotations')
            result = commit_sync(resolve(args.notes), resolve(args.store), resolve(args.report),
                                 _json(resolve(args.annotations)), workspace=args.workspace)
        else:
            if not args.output:
                parser.error('render requires a new --output path; preserve the baseline report')
            result = {'report': str(render_progress_report(resolve(args.report), resolve(args.store), resolve(args.output), replace=args.replace))}
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output and args.action != 'render':
            output = resolve(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('x', encoding='utf-8') as handle:
                handle.write(text + '\n')
            print(json.dumps({'saved': str(output), 'changed_sections': len(result.get('changed', []))}, ensure_ascii=False))
        else:
            print(text)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
