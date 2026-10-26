"""Normalize an actual tool artifact plus its invocation; never run/guess source coverage implicitly."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
from ut_diff_report.core import load_data
from ut_diff_report.coverage import parse_coverage

configure_cli()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--format', choices=('go', 'coveragepy', 'lcov', 'cobertura'), required=True)
    parser.add_argument('--invocation', type=Path, required=True, help='run_tests.py invocation.json, including real source context')
    parser.add_argument('--test-invocation', type=Path, help='original test invocation when --invocation is a separate export')
    parser.add_argument('--data-artifact', type=Path, help='intermediate coverage data hash-bound to the original test invocation')
    parser.add_argument('--project-id', choices=('A', 'B'), required=True)
    parser.add_argument('--tool', required=True)
    parser.add_argument('--tool-version', required=True)
    parser.add_argument('--scope', choices=('UT', 'MIXED', 'UNKNOWN'), required=True)
    parser.add_argument('--scope-evidence', action='append', required=True)
    parser.add_argument('--exclude', action='append', default=[], help='record actual native-tool exclusions; does not alter denominator')
    parser.add_argument('--unmeasured-file', action='append', default=[])
    parser.add_argument('--strip-prefix', help='explicit measured file-path prefix to normalize')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise FileExistsError('choose a fresh normalized coverage output')
        invocation = load_data(args.invocation)
        test_invocation = load_data(args.test_invocation) if args.test_invocation else invocation
        if not invocation.get('command') or not invocation.get('run_at'):
            raise ValueError('actual invocation command/time required')
        if invocation.get('timeout') or invocation.get('exit_code') != 0:
            raise ValueError('coverage execution incomplete/failed; keep raw evidence and mark uncollected instead of presenting a full denominator')
        if test_invocation.get('timeout') or test_invocation.get('exit_code') != 0 or not test_invocation.get('command'):
            raise ValueError('original test execution failed/incomplete or lacks invocation evidence')
        if args.test_invocation:
            if not args.data_artifact:
                raise ValueError('separate export requires the original intermediate --data-artifact')
            import hashlib
            intermediate_hash = hashlib.sha256(args.data_artifact.read_bytes()).hexdigest()
            if not any(a.get('sha256') == intermediate_hash and Path(a['path']).resolve() == args.data_artifact.resolve()
                       for a in test_invocation.get('produced_artifacts', [])):
                raise ValueError('intermediate coverage data does not match the original test invocation')
            explicit_data = False
            for part in invocation['command']:
                candidate = part.split('=', 1)[-1]
                if not candidate or (candidate.startswith('-') and '=' not in part):
                    continue
                try:
                    path = Path(candidate)
                    if not path.is_absolute():
                        path = Path(invocation['cwd']) / path
                    explicit_data |= path.resolve() == args.data_artifact.resolve()
                except (OSError, ValueError):
                    continue
            if not explicit_data:
                raise ValueError('export command must explicitly select the original intermediate data artifact')
        from datetime import datetime
        started = datetime.fromisoformat(invocation['run_at'].replace('Z', '+00:00')).timestamp()
        if args.input.stat().st_mtime < started - 2:
            raise ValueError('artifact predates invocation; stale coverage cannot be reused as a fresh collection')
        measured = parse_coverage(args.input, args.format, args.strip_prefix)
        recorded = invocation.get('produced_artifacts', [])
        if not any(a.get('sha256') == measured['artifact']['sha256'] and
                   Path(a['path']).resolve() == args.input.resolve() for a in recorded):
            raise ValueError('artifact is not hash-bound to this invocation; collect it with run_tests.py --fresh-output')
        if invocation.get('source_digest_before') != invocation.get('source_digest_after'):
            raise ValueError('source changed during coverage collection; preserve evidence and re-establish a stable source snapshot')
        if (test_invocation.get('source_digest_before') != test_invocation.get('source_digest_after') or
                test_invocation.get('source_digest_after') != invocation.get('source_digest_before')):
            raise ValueError('test and export do not use the same stable source fingerprint')
        if not measured['metrics']:
            raise ValueError('artifact has no measurable denominator; record uncollected/not applicable with reason')
        result = {**measured, 'project_id': args.project_id, 'collected': True, 'tool': args.tool,
            'tool_version': args.tool_version, 'command': test_invocation['command'], 'run_at': test_invocation['run_at'],
            'scope': args.scope, 'scope_evidence': args.scope_evidence, 'exclusions': args.exclude,
            'unmeasured_files': args.unmeasured_file, 'source_context': test_invocation.get('source_context', {})}
        if args.test_invocation:
            result['report_command'] = invocation['command']
            result['test_artifact'] = {'path': str(args.data_artifact), 'sha256': intermediate_hash}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(args.output)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, str(exc) + '\n')
