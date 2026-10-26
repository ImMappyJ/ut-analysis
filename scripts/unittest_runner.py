"""Child-process unittest reporter including successful subTest observations."""

import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
import time
import traceback
import unittest


class Result(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.records = []
        self.lifecycle_events = []
        self.active = False

    def startTest(self, test):
        super().startTest(test)
        self.active = True
        self.started = time.monotonic()
        self.record = {'name': test.id(), 'status': 'PASS', 'children': [], 'output': ''}
        self.output = io.StringIO()
        self.stdout = contextlib.redirect_stdout(self.output)
        self.stderr = contextlib.redirect_stderr(self.output)
        self.stdout.__enter__()
        self.stderr.__enter__()

    def stopTest(self, test):
        self.stderr.__exit__(None, None, None)
        self.stdout.__exit__(None, None, None)
        self.record['elapsed_seconds'] = time.monotonic() - self.started
        self.record['output'] += self.output.getvalue()
        self.records.append(self.record)
        self.active = False
        super().stopTest(test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record.update(status='FAIL', output=''.join(traceback.format_exception(*err)))

    def addError(self, test, err):
        super().addError(test, err)
        output = ''.join(traceback.format_exception(*err))
        if self.active:
            self.record.update(status='ERROR', output=output)
        else:
            self.lifecycle_events.append({'name': test.id(), 'status': 'ERROR', 'output': output})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if not self.active:
            self.lifecycle_events.append({'name': test.id(), 'status': 'SKIP', 'output': reason})
        elif isinstance(test, unittest.case._SubTest):
            self.record['children'].append({'name': test.id(), 'status': 'SKIP', 'output': reason})
        else:
            self.record.update(status='SKIP', output=reason)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        status = 'PASS' if err is None else 'FAIL' if issubclass(err[0], test.failureException) else 'ERROR'
        self.record['children'].append({'name': subtest.id(), 'status': status,
                                       'output': ''.join(traceback.format_exception(*err)) if err else ''})
        if err:
            self.record['status'] = 'ERROR' if status == 'ERROR' or self.record['status'] == 'ERROR' else 'FAIL'

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.record.update(status='FAIL', output='Unexpected success (expected-failure contract violated).')

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.record.update(status='SKIP', output='Expected failure: ' + ''.join(traceback.format_exception(*err)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--pattern', default='test*.py')
    parser.add_argument('--test-id', action='append', default=[])
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.project).resolve()))
    suite = (unittest.defaultTestLoader.loadTestsFromNames(args.test_id) if args.test_id else
             unittest.defaultTestLoader.discover(args.project, pattern=args.pattern))
    result = Result()
    suite.run(result)
    Path(args.output).write_text(json.dumps({'tests': result.records, 'lifecycle_events': result.lifecycle_events,
                                          'discovery_errors': unittest.defaultTestLoader.errors},
                                          ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
