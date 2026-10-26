"""Capture an explicit native test command, or use unittest reporting with subTest events."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
configure_cli()
from ut_diff_report.execution import capture, import_junit, parse_go_json, run_unittest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True, help='fresh directory in caller workspace')
    parser.add_argument('--framework', choices=('unittest', 'go', 'command'), required=True)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--junit', type=Path, help='native JUnit XML to import after command')
    parser.add_argument('--pattern', default='test*.py', help='unittest discovery pattern')
    parser.add_argument('--test-id', action='append', default=[], help='audited unittest ID; repeat to select pure UT scope')
    parser.add_argument('--fresh-output', type=Path, action='append', default=[],
                        help='coverage/reporter artifact that must not exist before the invocation')
    parser.add_argument('argv', nargs=argparse.REMAINDER, help='explicit command after --; no shell')
    args = parser.parse_args()
    try:
        if args.artifacts.exists() and any(args.artifacts.iterdir()):
            raise FileExistsError('artifacts directory must be empty; preserve older evidence')
        if args.timeout <= 0:
            raise ValueError('timeout must be positive')
        fresh_outputs = [p if p.is_absolute() else args.project / p for p in args.fresh_output]
        if any(p.exists() for p in fresh_outputs):
            raise FileExistsError('native output already exists; choose fresh artifact paths')
        junit_path = None
        if args.junit:
            junit_path = args.junit if args.junit.is_absolute() else args.project / args.junit
            if junit_path.exists():
                raise FileExistsError('JUnit output already exists; choose a fresh path to avoid stale observations')
        if args.framework == 'unittest':
            result = run_unittest(args.project.resolve(), args.artifacts, args.timeout, args.pattern, args.test_id)
        else:
            command = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
            if not command:
                raise ValueError('supply an audited native argv after --')
            result = capture(command, args.project.resolve(), args.artifacts, args.timeout)
            if args.framework == 'go':
                result.update(parse_go_json(result['stdout']))
            if junit_path:
                result.update(import_junit(junit_path))
        output = args.artifacts / 'results.json'
        import hashlib
        result['produced_artifacts'] = [{'path': str(p.resolve()),
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in fresh_outputs if p.is_file()]
        # The invocation ledger gains output hashes after the native command completed.
        invocation_path = args.artifacts / 'invocation.json'
        invocation = json.loads(invocation_path.read_text(encoding='utf-8'))
        invocation['produced_artifacts'] = result['produced_artifacts']
        invocation_path.write_text(json.dumps(invocation, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(output)
        if result['source_digest_before'] != result['source_digest_after']:
            print('Source digest changed during execution. Investigate before reporting unchanged source.', file=sys.stderr)
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')
