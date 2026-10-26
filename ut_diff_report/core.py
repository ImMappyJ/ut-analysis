"""Strict report contract, evidence accounting, and atomic offline rendering."""

from collections import Counter
from datetime import datetime
import difflib
from html import escape
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile

from . import __version__, TEMPLATE_VERSION

ROOT = Path(__file__).resolve().parents[1]
STATUSES = ('PASS', 'FAIL', 'SKIP', 'ERROR', 'NOT RUN')
MATCHES = ('EXACT', 'PARTIAL', 'A_ONLY', 'B_ONLY')


class ValidationError(ValueError):
    """Invalid contract or unverifiable accounting."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def load_data(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result

    def invalid(value):
        raise ValidationError('non-finite JSON number: ' + value)

    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=pairs,
                          parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(str(exc)) from exc


def check_schema(value, schema, document=None, location='$'):
    """Validate the documented JSON Schema subset used by this project's schema."""
    document = document or schema
    if '$ref' in schema:
        target = document
        for piece in schema['$ref'].removeprefix('#/').split('/'):
            target = target[piece]
        return check_schema(value, target, document, location)
    types = schema.get('type', [])
    types = [types] if isinstance(types, str) else types
    checks = {'object': isinstance(value, dict), 'array': isinstance(value, list),
              'string': isinstance(value, str), 'boolean': isinstance(value, bool),
              'null': value is None, 'integer': type(value) is int,
              'number': type(value) in (int, float) and math.isfinite(value)}
    require(not types or any(checks[t] for t in types), location + ': invalid type')
    if 'enum' in schema:
        require(value in schema['enum'], location + ': invalid enum')
    if 'const' in schema:
        require(value == schema['const'], location + ': unexpected version/value')
    if isinstance(value, dict):
        for key in schema.get('required', []):
            require(key in value, location + ': missing ' + key)
        props = schema.get('properties', {})
        if schema.get('additionalProperties') is False:
            require(not set(value) - set(props), location + ': unknown properties ' + str(set(value) - set(props)))
        for key, item in value.items():
            if key in props:
                check_schema(item, props[key], document, location + '.' + key)
    if isinstance(value, list):
        require(len(value) >= schema.get('minItems', 0), location + ': too few items')
        for index, item in enumerate(value):
            check_schema(item, schema.get('items', {}), document, f'{location}[{index}]')
    if isinstance(value, str):
        require(len(value.strip()) >= schema.get('minLength', 0), location + ': empty text')
        if 'pattern' in schema:
            require(re.search(schema['pattern'], value) is not None, location + ': invalid format')
    if type(value) in (int, float) and 'minimum' in schema:
        require(value >= schema['minimum'], location + ': below minimum')


def index_unique(items, label):
    result = {}
    for item in items:
        require(item['id'] not in result, label + ': duplicate id ' + item['id'])
        result[item['id']] = item
    return result


def effective_result(test_id, results):
    return results.get(test_id, {'test_id': test_id, 'status': 'NOT RUN',
                                'reason': '没有提供该入口的实际执行证据。', 'children': []})


def comparison(a, b):
    if not a or not b or 'NOT RUN' in (a['status'], b['status']):
        return 'UNKNOWN'
    # Child names across frameworks cannot establish scenario equivalence. Only compare
    # explicit, Agent-supplied semantic keys; otherwise missing comparable evidence is UNKNOWN.
    ac, bc = a.get('children', []), b.get('children', [])
    if ac or bc:
        if not ac or not bc or any(not c.get('scenario_key') for c in ac + bc):
            return 'UNKNOWN' if a['status'] == b['status'] else 'DIFFERENT'
        av = sorted((c['scenario_key'], c['status']) for c in ac)
        bv = sorted((c['scenario_key'], c['status']) for c in bc)
        return 'SAME' if a['status'] == b['status'] and av == bv else 'DIFFERENT'
    return 'SAME' if a['status'] == b['status'] else 'DIFFERENT'


def summarize(data):
    tests = {t['id']: t for t in data['test_cases'] if t['kind'] == 'unit'}
    results = {r['test_id']: r for r in data['execution_results']}
    summary = {'UT': {}, 'matching': dict.fromkeys(MATCHES, 0),
               'execution': dict.fromkeys(('SAME', 'DIFFERENT', 'UNKNOWN'), 0),
               'results': {}, 'modules': [], 'owners': []}
    for pid in ('A', 'B'):
        entries = [t for t in tests.values() if t['project_id'] == pid]
        counts = Counter(effective_result(t['id'], results)['status'] for t in entries)
        summary['UT'][pid] = len(entries)
        summary['results'][pid] = {s: counts[s] for s in STATUSES}
    for match in data['matches']:
        summary['matching'][match['status']] += 1
        a = effective_result(match['a'], results) if match.get('a') else None
        b = effective_result(match['b'], results) if match.get('b') else None
        if a and b:
            summary['execution'][comparison(a, b)] += 1
    for module in sorted(data['modules'], key=lambda x: x['id']):
        ids = {t['id'] for t in tests.values() if t['module_id'] == module['id']}
        ms = [m for m in data['matches'] if m.get('a') in ids or m.get('b') in ids]
        summary['modules'].append({'id': module['id'], 'module': module['name'],
            'a': sum(tests[i]['project_id'] == 'A' for i in ids),
            'b': sum(tests[i]['project_id'] == 'B' for i in ids),
            'exact': sum(m['status'] == 'EXACT' for m in ms),
            'partial': sum(m['status'] == 'PARTIAL' for m in ms),
            'aOnly': sum(m['status'] == 'A_ONLY' for m in ms),
            'bOnly': sum(m['status'] == 'B_ONLY' for m in ms),
            'resultDiff': sum(comparison(effective_result(m['a'], results) if m.get('a') else None,
                                         effective_result(m['b'], results) if m.get('b') else None) == 'DIFFERENT' for m in ms)})
    for owner in sorted(data.get('owners', []), key=lambda x: x['id']):
        mods = {m['id'] for m in data['modules'] if owner['id'] in m.get('owner_ids', [])}
        ids = {t['id'] for t in tests.values() if t['module_id'] in mods}
        ms = [m for m in data['matches'] if m.get('a') in ids or m.get('b') in ids]
        summary['owners'].append({'id': owner['id'], 'name': owner['name'], 'modules': len(mods),
            'A': sum(tests[i]['project_id'] == 'A' for i in ids),
            'B': sum(tests[i]['project_id'] == 'B' for i in ids),
            'matching': {s: sum(m['status'] == s for m in ms) for s in MATCHES},
            'results': {p: {s: sum(tests[i]['project_id'] == p and effective_result(i, results)['status'] == s for i in ids)
                           for s in STATUSES} for p in ('A', 'B')}})
    return summary


def validate(data):
    check_schema(data, load_data(ROOT / 'references/report.schema.json'))
    def timestamp(value):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            require(parsed.tzinfo is not None, 'timestamp needs timezone')
        except (TypeError, ValueError) as exc:
            raise ValidationError('expected ISO timestamp with timezone: ' + str(value)) from exc

    timestamp(data['report_metadata']['generated_at'])
    projects = index_unique(data['projects'], 'projects')
    mode = data['report_metadata'].get('mode', 'compare')
    require(set(projects) == ({'A'} if mode == 'audit' else {'A', 'B'}),
            'audit requires A only; compare/full require A and B exactly once')
    require(mode == 'compare' or data['schema_version'] == '1.1.0', 'audit/full require schema 1.1.0')
    for project in projects.values():
        context = project.get('git', {})
        if context.get('is_git'):
            require(bool(context.get('analysis_root')) and bool(context.get('branch')), 'Git metadata needs actual root and branch/detached label')
            require(context.get('sha') is None or re.fullmatch(r'[a-fA-F0-9]{40}|[a-fA-F0-9]{64}', context['sha']), 'invalid Git commit SHA')
            require(type(context.get('has_uncommitted_changes')) is bool, 'Git metadata needs explicit working-tree state')
    modules = index_unique(data['modules'], 'modules')
    owners = index_unique(data.get('owners', []), 'owners')
    tests = index_unique(data['test_cases'], 'test_cases')
    index_unique(data['matches'], 'matches')
    for module in modules.values():
        require(set(module.get('owner_ids', [])) <= set(owners), 'unknown owner in ' + module['id'])
        if module.get('priority') in ('P0', 'P1'):
            require(bool(module.get('priority_reason', '').strip()), 'priority requires business-impact reason')
    for test in tests.values():
        require(test['project_id'] in projects and test['module_id'] in modules, 'unknown project/module in ' + test['id'])
        p = test['path'].replace('\\', '/')
        require(not PurePosixPath(p).is_absolute() and '..' not in PurePosixPath(p).parts
                and not re.match(r'^[A-Za-z]:', p), 'test path must be relative within its project')
        require(test.get('end_line', test['line']) >= test['line'], 'invalid source range')
    seen = Counter()
    for match in data['matches']:
        a, b, status = match.get('a'), match.get('b'), match['status']
        require((status in ('EXACT', 'PARTIAL') and bool(a) and bool(b))
                or (status == 'A_ONLY' and bool(a) and not b)
                or (status == 'B_ONLY' and bool(b) and not a), 'match shape conflicts with status')
        for key, pid in ((a, 'A'), (b, 'B')):
            if key:
                require(key in tests and tests[key]['kind'] == 'unit' and tests[key]['project_id'] == pid,
                        'invalid match reference: ' + str(key))
                seen[key] += 1
        if a and b:
            require(tests[a]['module_id'] == tests[b]['module_id'], 'normalize business modules before matching')
        for key in match.get('related_test_ids', []):
            require(key in tests, 'unknown related test')
    unit_ids = {t['id'] for t in tests.values() if t['kind'] == 'unit'}
    if mode == 'audit':
        require(not data['matches'], 'audit has no artificial project B or Diff matches')
    else:
        require(set(seen) == unit_ids and all(n == 1 for n in seen.values()),
                'every unit entry must appear in exactly one main comparison row')
    result_ids = set()
    for result in data['execution_results']:
        tid = result['test_id']
        require(tid in tests and tid not in result_ids, 'duplicate/unknown execution test_id')
        result_ids.add(tid)
        if result['status'] == 'NOT RUN':
            require(bool(result.get('reason', '').strip()), 'NOT RUN requires a reason')
        else:
            require(bool(result.get('command')) and bool(result.get('run_at')) and bool(result.get('environment'))
                    and bool(result.get('evidence')), 'executed status requires command/time/environment/evidence')
            timestamp(result['run_at'])
            project = projects[tests[tid]['project_id']]
            if project.get('git', {}).get('sha'):
                from .quality import verify_source_context
                verify_source_context(project['git'], result.get('source_context'), 'test execution')
        keys = [c['scenario_key'] for c in result.get('children', []) if c.get('scenario_key')]
        require(len(keys) == len(set(keys)), 'duplicate child scenario_key within one entry')
        if result['status'] == 'PASS':
            require(not any(c['status'] in ('FAIL', 'ERROR', 'NOT RUN') for c in result.get('children', [])),
                    'PASS parent conflicts with failed/unexecuted child')
    for diff in data.get('differences', []):
        require(diff['match_id'] in {m['id'] for m in data['matches']}, 'unknown difference match_id')
    expected = summarize(data)
    if 'summary' in data:
        require(data['summary'] == expected, 'supplied summary does not equal computed summary')
    if mode in ('audit', 'full'):
        from .quality import validate_quality
        validate_quality(data)
    return expected


def code_diff(a, b, a_line=1, b_line=1):
    left, right = a.splitlines(), b.splitlines()
    rows = []
    groups = list(difflib.SequenceMatcher(None, left, right, autojunk=False).get_grouped_opcodes(3))
    if not groups:
        groups = [[('equal', 0, min(len(left), 10), 0, min(len(right), 10))]]
    for group in groups:
        if rows:
            rows.append({'gap': True})
        for tag, i, ie, j, je in group:
            for k in range(max(ie - i, je - j)):
                rows.append({'a': [a_line + i + k, left[i + k], 'context' if tag == 'equal' else 'removed'] if i + k < ie else None,
                             'b': [b_line + j + k, right[j + k], 'context' if tag == 'equal' else 'added'] if j + k < je else None})
    return rows


def view_data(data):
    summary = validate(data)
    modules = {m['id']: m for m in data['modules']}
    owners = {o['id']: o['name'] for o in data.get('owners', [])}
    results = {r['test_id']: r for r in data['execution_results']}
    records, excluded = [], []
    for t in sorted(data['test_cases'], key=lambda t: (t['project_id'], t['path'], t['line'], t['id'])):
        m = modules[t['module_id']]
        result = effective_result(t['id'], results)
        r = {'id': t['id'], 'repo': t['project_id'], 'path': t['path'], 'package': t.get('suite', ''),
             'module': m['name'], 'moduleId': m['id'], 'name': t['name'], 'line': t['line'],
             'endLine': t.get('end_line', t['line']), 'goal': t['goal'], 'priority': m.get('priority', '未评级'),
             'owner': ' / '.join(owners[i] for i in m.get('owner_ids', [])) or '未指定',
             'ownerIds': m.get('owner_ids', []), 'scope': t['kind'], 'scopeReason': t.get('scope_reason', ''),
             'assertions': t.get('assertions', []), 'helperAssertions': [], 'helpers': t.get('helpers', []),
             'globalRefs': t.get('globals', []), 'runs': t.get('subtests', []), 'tables': t.get('parameter_tables', []),
             'scenarioLabels': t.get('scenarios', []), 'expectations': t.get('expectations', []),
             'oracleWarning': t.get('assertion_note', ''), 'code': t['code'], 'inputs': t.get('inputs', []),
             'evidence': t['evidence'],
             'result': {'status': result['status'], 'reason': result.get('reason', ''),
                        'elapsed': result.get('elapsed_seconds'), 'output': '\n'.join(filter(None, (result.get('stdout'), result.get('stderr')))),
                        'children': [{**c, 'elapsed': c.get('elapsed_seconds'), 'output': c.get('output', '')} for c in result.get('children', [])],
                        'startedAt': result.get('run_at'), 'goCommand': result.get('command', []),
                        'environment': result.get('environment', {}), 'evidence': result.get('evidence', []),
                        'cached': result.get('cached', False), 'packageExit': result.get('exit_code')}}
        r['result']['history'] = result.get('history', [])
        r['result']['sourceContext'] = result.get('source_context', {})
        (records if t['kind'] == 'unit' else excluded).append(r)
    by_id = {r['id']: r for r in records}
    pairs = []
    for match in data['matches']:
        a, b = by_id.get(match.get('a')), by_id.get(match.get('b'))
        base = a or b
        execution = comparison(effective_result(a['id'], results) if a else None,
                               effective_result(b['id'], results) if b else None)
        pairs.append({'id': 'ut-pair-' + match['id'], 'sourceId': match['id'],
            'a': match.get('a'), 'b': match.get('b'), 'match': match['status'],
            'execution': execution, 'executionNote': '执行对比使用顶层状态；子场景仅按明确的场景键比较。缺少运行或可比子场景证据时为未确认。',
            'evidence': match['evidence'], 'relatedTestIds': match.get('related_test_ids', []),
            'module': base['module'], 'moduleId': base['moduleId'], 'priority': base['priority'],
            'ownerIds': base['ownerIds'], 'difference': match['status'] != 'EXACT' or execution != 'SAME'
                or any(r and r['result']['status'] != 'PASS' for r in (a, b)),
            'diff': code_diff(a['code'] if a else '', b['code'] if b else '', a['line'] if a else 1, b['line'] if b else 1),
            'auxDiff': [], 'outputDiff': code_diff(a['result']['output'] if a else '', b['result']['output'] if b else ''),
            'notes': [d for d in data.get('differences', []) if d['match_id'] == match['id']]})
    pairs.sort(key=lambda p: (p['module'], p['priority'], (by_id.get(p['a']) or by_id.get(p['b']))['path'], p['id']))
    projects = {p['id']: {'name': p['name'], 'branch': p.get('branch', ''), 'head': p.get('revision', ''),
                          'git': p.get('git', {}),
                          'testFiles': p.get('test_file_count', len({t['path'] for t in data['test_cases'] if t['project_id'] == p['id']})),
                          'frameworks': p.get('frameworks', []), 'scan': p.get('scan', {})} for p in data['projects']}
    view = {'meta': {**data['report_metadata'], 'projects': projects,
                     'mode': data['report_metadata'].get('mode', 'compare'), 'skillVersion': __version__,
                     'templateVersion': TEMPLATE_VERSION, 'capabilities': ['ut-card-deep-link-v1']}, 'summary': summary, 'records': records,
            'excluded': excluded, 'pairs': pairs, 'owners': data.get('owners', []), 'modules': data['modules']}
    if data['report_metadata'].get('mode') in ('audit', 'full'):
        from .quality import evaluate_quality
        view['quality'] = data['quality']
        view['quality_evaluation'] = evaluate_quality(data)
    return view


def html_text(data):
    return view_html(view_data(data))


def view_html(view):
    """Render an existing validated inventory without recomputing historical judgments."""
    payload = json.dumps(view, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    for c, replacement in (('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')):
        payload = payload.replace(c, replacement)
    text = (ROOT / 'assets/report_template.html').read_text(encoding='utf-8')
    quality_mode = view['meta']['mode'] in ('audit', 'full')
    substitutions = {'__REPORT_CSS__': (ROOT / 'assets/report.css').read_text(encoding='utf-8') +
                       ((ROOT / 'assets/quality.css').read_text(encoding='utf-8') if quality_mode else '') +
                       (ROOT / 'assets/progress.css').read_text(encoding='utf-8'),
                     '__REPORT_JS__': (ROOT / 'assets/report.js').read_text(encoding='utf-8') +
                       ('\n' + (ROOT / 'assets/quality.js').read_text(encoding='utf-8') if quality_mode else '') +
                       '\n' + (ROOT / 'assets/progress.js').read_text(encoding='utf-8'),
                     '__UT_DATA__': payload, '__REPORT_TITLE__': escape(view['meta']['title'])}
    for marker in substitutions:
        require(text.count(marker) == 1, 'template requires exactly one ' + marker)
    return re.sub('|'.join(map(re.escape, substitutions)), lambda m: substitutions[m[0]], text)


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.capture = False
        self.payloads = []
        self.current = []
        self.ids = Counter()
        self.external = []
        self.script_count = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids[attrs['id']] += 1
        if tag in ('script', 'link', 'iframe', 'img') and (attrs.get('src') or attrs.get('href')):
            self.external.append(attrs.get('src') or attrs.get('href'))
        if tag == 'script':
            self.script_count += 1
            if attrs.get('id') == 'ut-data' and attrs.get('type') == 'application/json':
                self.capture = True

    def handle_data(self, text):
        if self.capture:
            self.current.append(text)

    def handle_endtag(self, tag):
        if tag == 'script' and self.capture:
            self.payloads.append(''.join(self.current))
            self.current = []
            self.capture = False


def validate_html(path):
    text = Path(path).read_text(encoding='utf-8')
    parser = ReportParser()
    parser.feed(text)
    require(len(parser.payloads) == 1 and parser.script_count == 2, 'invalid inline script structure')
    require(not parser.external, 'report must have no external runtime assets')
    require(all(n == 1 for n in parser.ids.values()), 'duplicate static element ids')
    static_text = text.replace(parser.payloads[0], '', 1)
    require(not re.search(r'__(REPORT_(CSS|JS|TITLE)|UT_DATA)__', static_text), 'unexpanded template placeholder')
    require('Content-Security-Policy' in text, 'missing content security policy')
    view = json.loads(parser.payloads[0])
    for pid in ('A', 'B'):
        require(sum(view['summary']['results'][pid].values()) == view['summary']['UT'][pid], 'result counts mismatch')
    require(len(view['pairs']) == sum(view['summary']['matching'].values()), 'match count mismatch')
    return view['summary']


def render(data, *, workspace, output=None, replace=False):
    workspace = Path(workspace).resolve()
    target = Path(output) if output else Path('docs/ut_result.html')
    target = target if target.is_absolute() else workspace / target
    target = target.resolve()
    if target.exists() and not replace:
        raise FileExistsError(f'{target} exists; explicit regeneration requires --replace')
    text = html_text(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', suffix='.tmp',
                                         dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        validate_html(temporary)
        if replace:
            os.replace(temporary, target)
        else:
            # Atomic create without clobbering a report created concurrently.
            os.link(temporary, target)
            temporary.unlink()
        return target
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
