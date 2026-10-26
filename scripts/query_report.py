"""Look up UT cards in an existing offline report; never execute report JavaScript/tests."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
from ut_diff_report.card_query import get_ut_card, get_ut_cards

configure_cli()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument('--name', help='full UT name or exact unqualified function name')
    identity.add_argument('--id', dest='test_id', help='unique UT ID from a returned candidate')
    identity.add_argument('--file', help='return all cards for this exact test file path')
    parser.add_argument('--project-root', help='explicit absolute project root for an absolute --file')
    parser.add_argument('--project', choices=('A', 'B'))
    parser.add_argument('--path', help='exact project-relative test path to disambiguate repeated names')
    parser.add_argument('--match', choices=('exact', 'contains'))
    parser.add_argument('--limit', type=int, help='maximum name/ID candidates, 1..200; default 30')
    parser.add_argument('--output', type=Path, help='fresh JSON file; stdout is JSON when omitted')
    parser.add_argument('--detail', action='store_true', help='include complete code, assertions and logs; default is summary')
    parser.add_argument('--progress', type=Path, help='explicit progress ledger directory; verifies current notes hashes')
    args = parser.parse_args()
    try:
        if args.file is not None:
            if args.path is not None or args.match is not None or args.limit is not None:
                parser.error('--file cannot be combined with --path, --match or --limit; returns all cards')
            result = get_ut_cards(args.report, args.file, project=args.project, project_root=args.project_root)
        else:
            if args.project_root is not None:
                parser.error('--project-root requires --file')
            result = get_ut_card(args.report, args.name, project=args.project, path=args.path,
                                 test_id=args.test_id, match=args.match or 'exact',
                                 limit=args.limit if args.limit is not None else 30)
        from ut_diff_report.progress import get_ut_context
        from ut_diff_report.card_query import summarize_result
        if args.progress:
            if args.match == 'contains':
                parser.error('progress queries require exact identity')
            result = get_ut_context(args.report, args.name, file_path=args.file, project=args.project,
                                    path=args.path, test_id=args.test_id, project_root=args.project_root,
                                    progress_path=args.progress, detail=args.detail,
                                    limit=args.limit if args.limit is not None else 30)
        elif not args.detail:
            result = summarize_result(result)
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x', encoding='utf-8', newline='\n') as handle:
                handle.write(text)
            print(args.output)
        else:
            print(text, end='')
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
