"""Query stored product requirements, UT quality and repair progress from offline HTML."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
from ut_diff_report.report_context import get_report_context

configure_cli()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--section', choices=('all','requirements','quality','progress'), default='all')
    identity = parser.add_mutually_exclusive_group()
    for flag, dest in (('name','ut_name'),('id','test_id'),('file','file_path'),
                       ('requirement','requirement_id'),('issue','issue_id'),('progress-id','progress_id')):
        identity.add_argument('--'+flag, dest=dest)
    parser.add_argument('--project', choices=('A','B'))
    parser.add_argument('--module', help='exact stable module ID from report')
    parser.add_argument('--path', help='project-relative UT path to disambiguate a name')
    parser.add_argument('--project-root', help='explicit root for an absolute --file')
    parser.add_argument('--progress', dest='progress_path', type=Path)
    parser.add_argument('--detail', action='store_true')
    parser.add_argument('--limit', type=int, default=30)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--output', type=Path, help='write to a fresh JSON file, returning counts only')
    args = vars(parser.parse_args())
    output = args.pop('output')
    report = args.pop('report')
    try:
        result = get_report_context(report, **args)
        payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
            print(json.dumps({'saved':str(output),'status':result['status'],
                              'totals':{k:result[k]['total'] for k in ('requirements','tests','progress') if k in result}},ensure_ascii=False))
        else:
            print(payload, end='')
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc)+'\n')


if __name__ == '__main__':
    main()
