"""Evidence capture without semantic matching or source rewriting."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def source_digest(project):
    """Hash analysis inputs, including fixtures/config; exclude documented generated evidence/cache.

    Link targets are recorded without reading files outside the selected source directory.
    """
    project = Path(project).resolve()
    h = hashlib.sha256()
    excluded = {'.git', '__pycache__', '.venv', 'venv', 'node_modules', 'vendor', '.artifacts', '.local',
                '.pytest_cache', '.mypy_cache', '.ruff_cache', '.tox', '.coverage', 'htmlcov'}
    for directory, dirs, files in os.walk(project, followlinks=False):
        base = Path(directory)
        relative_dir = base.relative_to(project)
        dirs[:] = sorted(d for d in dirs if d not in excluded and
                         (relative_dir / d).as_posix() != 'docs/ut-diff')
        links = [d for d in dirs if (base / d).is_symlink()]
        dirs[:] = [d for d in dirs if d not in links]
        for name in sorted(files + links):
            path = base / name
            relative = path.relative_to(project)
            if name in excluded or name.startswith('.coverage.') or relative.as_posix() == 'docs/ut_result.html':
                continue
            h.update(relative.as_posix().encode('utf-8') + b'\0')
            if path.is_symlink():
                h.update(b'link:' + os.fsencode(os.readlink(path)))
            elif path.is_file():
                with path.open('rb') as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b''):
                        h.update(block)
            h.update(b'\0')
    return h.hexdigest()


def capture(command, cwd, artifacts, timeout=120):
    """Run explicit argv with no shell; caller must review tests' external effects first."""
    artifacts = Path(artifacts).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    before = source_digest(cwd)
    started = time.monotonic()
    from .git_context import inspect
    source_context = inspect(cwd)
    process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8'},
                               start_new_session=os.name != 'nt')
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, check=False)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    outcome = {'command': list(command), 'cwd': str(Path(cwd).resolve()), 'run_at': stamp,
        'elapsed_seconds': time.monotonic() - started, 'exit_code': process.returncode,
        'timeout': timed_out, 'environment': {'os': platform.system(), 'platform': platform.platform(),
                                             'python': platform.python_version()},
        'stdout': stdout.decode('utf-8', errors='replace'), 'stderr': stderr.decode('utf-8', errors='replace'),
        'source_digest_before': before, 'source_digest_after': source_digest(cwd)}
    outcome['source_context'] = source_context
    outcome['source_context_after'] = inspect(cwd)
    (artifacts / 'invocation.json').write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return outcome


def run_unittest(project, artifacts, timeout=120, pattern='test*.py', test_ids=None):
    artifacts = Path(artifacts).resolve()
    result_file = artifacts / 'unittest.json'
    if result_file.exists():
        raise FileExistsError('use a fresh execution evidence directory')
    command = [sys.executable, str(ROOT / 'scripts/unittest_runner.py'), '--project', str(Path(project).resolve()),
               '--output', str(result_file), '--pattern', pattern]
    for test_id in test_ids or []:
        command.extend(['--test-id', test_id])
    outcome = capture(command, project, artifacts, timeout)
    detail = json.loads(result_file.read_text(encoding='utf-8')) if result_file.exists() else {'tests': []}
    return {**outcome, **detail}


def parse_go_json(text):
    records = {}
    package_errors = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        package, name = event.get('Package', ''), event.get('Test')
        if not name:
            if event.get('Output'):
                package_errors.append(event['Output'])
            continue
        record = records.setdefault((package, name), {'name': name, 'package': package, 'status': 'ERROR', 'output': ''})
        record['output'] += event.get('Output', '')
        if event.get('Action') in ('pass', 'fail', 'skip'):
            record['status'] = {'pass': 'PASS', 'fail': 'FAIL', 'skip': 'SKIP'}[event['Action']]
            record['elapsed_seconds'] = event.get('Elapsed', 0)
    roots = []
    for (package, name), record in records.items():
        if '/' not in name:
            record['children'] = [r for (p, n), r in records.items() if p == package and n.startswith(name + '/')]
            roots.append(record)
    return {'tests': roots, 'package_output': ''.join(package_errors)}


def import_junit(path):
    """Import observed instances only. The Agent must map instances to static templates."""
    raw = Path(path).read_bytes()
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('DTD/entity declarations are not accepted')
    root = ET.fromstring(raw)
    tests = []
    for case in root.iter('testcase'):
        status, messages = 'PASS', []
        for child in case:
            if child.tag in ('error', 'failure', 'skipped'):
                status = {'error': 'ERROR', 'failure': 'FAIL', 'skipped': 'SKIP'}[child.tag]
                messages.append(child.get('message', '') + '\n' + (child.text or ''))
        tests.append({'name': case.get('name', ''), 'suite': case.get('classname', ''),
                      'path': case.get('file', ''), 'line': case.get('line'), 'status': status,
                      'elapsed_seconds': float(case.get('time', 0)), 'output': '\n'.join(messages)})
    return {'tests': tests, 'source': str(path), 'limitation': 'Imported XML has no independently verified command/time; attach invocation evidence before claiming an executed result.'}
