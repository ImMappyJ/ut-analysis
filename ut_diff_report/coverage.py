"""Read measured coverage artifacts. Never estimate metrics from source/test counts."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

METRICS = ('line', 'branch', 'function', 'statement', 'condition', 'mutation')


def percentage(metric):
    return round(100 * metric['covered'] / metric['total'], 6) if metric and metric['total'] else None


def counts(covered, total):
    if type(covered) is not int or type(total) is not int or not 0 <= covered <= total:
        raise ValueError('impossible measured coverage numerator/denominator')
    return {'covered': covered, 'total': total}


def aggregate(files):
    metrics = {}
    for file in files:
        for key, value in file['metrics'].items():
            value = counts(value['covered'], value['total'])
            target = metrics.setdefault(key, {'covered': 0, 'total': 0})
            target['covered'] += value['covered']
            target['total'] += value['total']
    return metrics


def go_profile(text):
    lines = text.splitlines()
    if not lines or not re.fullmatch(r'mode: (set|count|atomic)', lines[0].strip()):
        raise ValueError('invalid Go coverprofile mode')
    segments = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        match = re.fullmatch(r'(.+):(\d+)\.(\d+),(\d+)\.(\d+)\s+(\d+)\s+(\d+)', line.strip())
        if not match:
            raise ValueError('invalid Go coverprofile segment')
        path, *values = match.groups()
        start, column, end, end_column, statements, hit = map(int, values)
        key = (path, start, column, end, end_column)
        if key in segments and segments[key][0] != statements:
            raise ValueError('inconsistent repeated Go segment denominator')
        segments[key] = (statements, max(hit, segments.get(key, (0, 0))[1]))
    by_file = defaultdict(lambda: {'covered': 0, 'total': 0})
    missed = defaultdict(list)
    for (path, start, column, end, end_column), (statements, hit) in segments.items():
        by_file[path]['total'] += statements
        by_file[path]['covered'] += statements if hit else 0
        if statements and not hit:
            missed[path].append({'start_line': start, 'end_line': end, 'start_column': column, 'end_column': end_column})
    # Go block statement coverage does not define an executable-line or branch denominator.
    return [{'path': path, 'metrics': {'statement': value}, 'uncovered_blocks': missed[path]}
            for path, value in sorted(by_file.items())]


def python_json(text):
    data = json.loads(text)
    files = []
    for path, item in sorted(data['files'].items()):
        summary = item.get('summary', {})
        metrics = {}
        if 'covered_lines' in summary and 'num_statements' in summary:
            metrics['line'] = counts(summary['covered_lines'], summary['num_statements'])
        elif 'executed_lines' in item and 'missing_lines' in item:
            executed, missing = set(item['executed_lines']), set(item['missing_lines'])
            if executed & missing:
                raise ValueError('overlapping covered/missing executable lines')
            metrics['line'] = counts(len(executed), len(executed | missing))
        if 'covered_branches' in summary and 'num_branches' in summary:
            metrics['branch'] = counts(summary['covered_branches'], summary['num_branches'])
        files.append({'path': path, 'metrics': metrics, 'uncovered_lines': item.get('missing_lines', []),
                      'uncovered_branches': item.get('missing_branches', [])})
    return files


def lcov(text):
    files = []
    item = None
    for line in text.splitlines() + ['end_of_record']:
        if line.startswith('SF:'):
            if item is not None:
                raise ValueError('LCOV record missing end_of_record')
            item = {'path': line[3:], 'lines': {}, 'branches': {}, 'functions': {}, 'totals': {}}
        elif item is not None:
            if line.startswith('DA:'):
                number, hit, *_ = line[3:].split(',')
                item['lines'][int(number)] = max(int(hit), item['lines'].get(int(number), 0))
            elif line.startswith('BRDA:'):
                number, block, branch, taken = line[5:].split(',')
                item['branches'][(number, block, branch)] = 0 if taken == '-' else int(taken)
            elif line.startswith('FNDA:'):
                hit, name = line[5:].split(',', 1)
                item['functions'][name] = int(hit)
            elif any(line.startswith(k + ':') for k in ('LF', 'LH', 'BRF', 'BRH', 'FNF', 'FNH')):
                key, value = line.split(':', 1)
                item['totals'][key] = int(value)
            elif line == 'end_of_record':
                metrics = {}
                for key, collection, total_key, hit_key in (
                        ('line', 'lines', 'LF', 'LH'), ('branch', 'branches', 'BRF', 'BRH'),
                        ('function', 'functions', 'FNF', 'FNH')):
                    observed = item[collection]
                    totals = item['totals']
                    if observed:
                        value = counts(sum(v > 0 for v in observed.values()), len(observed))
                        if total_key in totals and totals[total_key] != value['total']:
                            raise ValueError('LCOV detail/summary denominator mismatch')
                        if hit_key in totals and totals[hit_key] != value['covered']:
                            raise ValueError('LCOV detail/summary numerator mismatch')
                        metrics[key] = value
                    elif total_key in totals and hit_key in totals:
                        metrics[key] = counts(totals[hit_key], totals[total_key])
                files.append({'path': item['path'], 'metrics': metrics,
                              'uncovered_lines': sorted(n for n, hits in item['lines'].items() if not hits),
                              'uncovered_branches': [list(k) for k, hits in item['branches'].items() if not hits]})
                item = None
    return files


def cobertura(text):
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('DTD/entity declarations are not accepted')
    root = ET.fromstring(text)
    files = {}
    for cls in root.iter('class'):
        path = cls.get('filename')
        if not path:
            continue
        file = files.setdefault(path, {'lines': {}, 'branches': {}})
        for line in cls.findall('./lines/line'):
            number, hits = int(line.attrib['number']), int(line.attrib['hits'])
            file['lines'][number] = max(hits, file['lines'].get(number, 0))
            condition = re.search(r'\((\d+)/(\d+)\)', line.get('condition-coverage', ''))
            if condition:
                value = counts(int(condition[1]), int(condition[2]))
                if number in file['branches'] and file['branches'][number] != value:
                    raise ValueError('ambiguous duplicate Cobertura branch counts')
                file['branches'][number] = value
    result = []
    for path, file in sorted(files.items()):
        metrics = {'line': counts(sum(h > 0 for h in file['lines'].values()), len(file['lines']))}
        if file['branches']:
            metrics['branch'] = counts(sum(v['covered'] for v in file['branches'].values()),
                                       sum(v['total'] for v in file['branches'].values()))
        result.append({'path': path, 'metrics': metrics,
                       'uncovered_lines': sorted(n for n, h in file['lines'].items() if not h),
                       'uncovered_branches': [{'line': n, **v} for n, v in file['branches'].items() if v['covered'] < v['total']]})
    if not result and all(k in root.attrib for k in ('lines-covered', 'lines-valid')):
        metrics = {'line': counts(int(root.attrib['lines-covered']), int(root.attrib['lines-valid']))}
        if 'branches-covered' in root.attrib and 'branches-valid' in root.attrib:
            metrics['branch'] = counts(int(root.attrib['branches-covered']), int(root.attrib['branches-valid']))
        # Explicit aggregate-only path signals no module/file attribution is possible.
        result.append({'path': '<aggregate-only>', 'metrics': metrics, 'uncovered_lines': [], 'uncovered_branches': []})
    return result


def parse_coverage(path, fmt, strip_prefix=None):
    raw = Path(path).read_bytes()
    text = raw.decode('utf-8-sig')
    parsers = {'go': go_profile, 'coveragepy': python_json, 'lcov': lcov, 'cobertura': cobertura}
    if fmt not in parsers:
        raise ValueError('unsupported coverage format: ' + fmt)
    files = parsers[fmt](text)
    if strip_prefix:
        prefix = strip_prefix.replace('\\', '/').rstrip('/') + '/'
        for file in files:
            file['path'] = file['path'].replace('\\', '/').removeprefix(prefix)
    if len({f['path'] for f in files}) != len(files):
        raise ValueError('duplicate coverage file records; merge with the native tool first')
    return {'artifact': {'path': str(Path(path)), 'sha256': hashlib.sha256(raw).hexdigest()},
            'metrics': aggregate(files), 'files': files,
            'denominator': {'go': 'Go instrumented block statement counts, not executable lines or branches.',
                'coveragepy': 'coverage.py executable source lines and reported branch exits.',
                'lcov': 'LCOV executable lines, branches and functions from DA/BRDA/FNDA or LF/LH summaries.',
                'cobertura': 'Cobertura reported executable lines and detailed branch condition counts.'}[fmt]}
