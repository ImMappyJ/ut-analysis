"""Incremental, evidence-labelled repair notes. Semantic annotations belong to the Agent."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .core import require, validate_html, view_html
from .card_query import _read_report, _name_matches, get_ut_card, get_ut_cards, summarize_result

STATES = ('PLANNED', 'IN_PROGRESS', 'IMPLEMENTED', 'BLOCKED', 'DEFERRED', 'ACCEPTED_DIFFERENCE', 'CONFLICT')
CHANGES = ('UNKNOWN', 'UNCHANGED', 'MODIFIED', 'ADDED', 'REMOVED', 'REVERTED')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda x: require(False, 'invalid JSON constant'))


def _inside(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    require(path.is_relative_to(root) and path != root, 'path must stay within workspace: ' + str(path))
    return path


def _sections(notes):
    raw = Path(notes).read_bytes()
    lines = raw.decode('utf-8-sig').splitlines(keepends=True)
    sections, current, fence = {}, None, None
    for n, line in enumerate(lines, 1):
        f = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line.rstrip('\r\n'))
        if f:
            marker, suffix = f.groups()
            if fence is None:
                # Backtick info strings cannot themselves contain backticks.
                if marker[0] != '`' or '`' not in suffix:
                    fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1] and not suffix.strip():
                fence = None
        heading = re.match(r'^## ([^\n\r]+)', line) if fence is None else None
        if heading:
            title = heading[1].strip()
            # Task labels survive title edits; ordinary headings use the full title.
            key = re.split(r'[:：]', title, maxsplit=1)[0].strip()
            require(key not in sections, 'duplicate section key: ' + key)
            current = {'key': key, 'title': title, 'line': n, 'text': ''}
            sections[key] = current
        if current is not None:
            current['text'] += line
    for section in sections.values():
        section['sha256'] = digest(section['text'].encode('utf-8'))
    return digest(raw), sections


def _state(store):
    path = Path(store).resolve() / 'state.json'
    _inside(Path(store), path)
    if not path.exists():
        return {'schema_version': '1.0.0', 'revision': None, 'sections': {}, 'history': []}
    state = _json(path)
    require(state.get('schema_version') == '1.0.0', 'unsupported progress schema')
    revision = state.get('revision')
    require(isinstance(revision, str) and re.fullmatch('[a-f0-9]{64}', revision), 'invalid progress revision')
    snapshot = _inside(path.parent, path.parent / 'snapshots' / (revision + '.json'))
    require(snapshot.is_file() and digest(snapshot.read_bytes()) == revision, 'progress snapshot missing or changed')
    require(_json(snapshot) == {k: v for k, v in state.items() if k != 'revision'}, 'progress state differs from immutable snapshot')
    return state


def _binding(report):
    _, sha, view, _ = _read_report(report)
    return view['meta'].get('baseline_report_sha256', sha)


def _content_binding(view):
    baseline = copy.deepcopy(view)
    baseline.pop('progress', None)
    for key in ('baseline_report_sha256', 'presentation', 'capabilities'):
        baseline['meta'].pop(key, None)
    return digest(json.dumps(baseline, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8'))


def prepare_sync(notes, store, report, *, workspace, refresh_sections=None):
    workspace = Path(workspace).resolve()
    notes, store = _inside(workspace, notes), _inside(workspace, store)
    state = _state(store)
    binding = _binding(report)
    _, physical_sha, view, _ = _read_report(report)
    content_binding = _content_binding(view)
    if state.get('revision') and not state.get('baseline_data_sha256'):
        require(physical_sha == state.get('baseline_report_sha256'),
                'older ledger migration requires the exact preserved baseline file, not a derived report')
    require(state.get('baseline_report_sha256', binding) == binding, 'progress belongs to a different report snapshot; explicitly create/rebind a ledger')
    require(state.get('baseline_data_sha256', content_binding) == content_binding, 'baseline report inventory/evidence has changed')
    require(state.get('source_path', notes.relative_to(workspace).as_posix()) == notes.relative_to(workspace).as_posix(), 'different notes source; create a separate ledger')
    sha, sections = _sections(notes)
    refresh_sections = refresh_sections or []
    require(isinstance(refresh_sections, list) and all(isinstance(k, str) and k in sections for k in refresh_sections), 'refresh_sections must name existing task sections')
    previous = state['sections']
    changed = [s for key, s in sections.items() if key in refresh_sections or previous.get(key, {}).get('sha256') != s['sha256'] or previous.get(key, {}).get('removed')]
    removed = [key for key, s in previous.items() if key not in sections and not s.get('removed')]
    return {'schema_version': '1.0.0', 'document_sha256': sha, 'baseline_report_sha256': binding, 'baseline_data_sha256': content_binding,
            'base_revision': state['revision'], 'changed': changed, 'removed': removed,
            'section_count': len(sections), 'unchanged_count': len(sections) - len(changed),
            'needs_analysis': bool(changed or removed),
            'refresh_sections': sorted(set(refresh_sections)),
            'source_path': notes.relative_to(workspace).as_posix()}


def _validate_items(items, source):
    require(isinstance(items, list), 'section items must be a list')
    seen = set()
    for item in items:
        require(isinstance(item, dict), 'invalid progress item')
        for key in ('issue_id', 'summary', 'reason', 'next_step', 'owner', 'priority', 'reported_at', 'quote'):
            require(isinstance(item.get(key), str) and bool(item[key].strip()), 'missing progress field: ' + key)
        require(item['issue_id'] not in seen, 'duplicate issue_id within section')
        seen.add(item['issue_id'])
        require(item['quote'] in source['text'], 'quote must be verbatim evidence in this section')
        require(item.get('status') in STATES and item.get('change') in CHANGES, 'invalid progress state')
        require(item['priority'] in ('P0', 'P1', 'UNCLASSIFIED'), 'invalid priority')
        targets = item.get('targets')
        require(isinstance(targets, list), 'targets must be a list; candidates may have none')
        identities = set()
        for target in targets:
            require(target.get('project') in ('A', 'B'), 'target project must be A/B')
            require(isinstance(target.get('name'), str) and bool(target['name'].strip()), 'target name required')
            path = target.get('path', '')
            require(isinstance(path, str) and bool(path) and '\\' not in path and not path.startswith('/')
                    and ':' not in path and '..' not in path.split('/'), 'target requires a safe project-relative POSIX path')
            identity = (target['project'], path, target['name'])
            require(identity not in identities, 'duplicate target')
            identities.add(identity)
        verification = item.get('verification', {})
        require(verification.get('status') in ('PASS', 'FAIL', 'SKIP', 'ERROR', 'NOT RUN', 'UNKNOWN'), 'invalid documented result')
        require(isinstance(verification.get('scope'), str) and bool(verification['scope'].strip()), 'verification scope required')
        require(not any(k in item for k in ('evidence_state', 'source_state', 'matched_test_ids')), 'derived evidence fields cannot be authored')
        for event in item.get('timeline', []):
            require(event.get('status') in STATES and isinstance(event.get('reported_at'), str)
                    and isinstance(event.get('summary'), str) and event.get('quote')
                    and event['quote'] in source['text'], 'timeline requires dated source evidence')


def _write_json(path, data):
    raw = (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(raw)
        temp = Path(handle.name)
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def commit_sync(notes, store, report, annotations, *, workspace):
    workspace = Path(workspace).resolve()
    store = _inside(workspace, store)
    store.mkdir(parents=True, exist_ok=True)
    lock = store / '.sync.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('another sync holds .sync.lock; inspect ownership before retrying')
    try:
        os.close(fd)
        refresh = annotations.get('refresh_sections', [])
        if refresh:
            require(isinstance(annotations.get('correction_reason'), str) and bool(annotations['correction_reason'].strip()), 'explicit re-annotation requires correction_reason')
        plan = prepare_sync(notes, store, report, workspace=workspace, refresh_sections=refresh)
        require(annotations.get('base_revision') == plan['base_revision'], 'stale base revision; prepare again')
        require(annotations.get('document_sha256') == plan['document_sha256'], 'notes changed after analysis; prepare again')
        require(annotations.get('removed') == plan['removed'], 'removed sections must be explicitly acknowledged')
        batches = annotations.get('sections', [])
        require(isinstance(batches, list) and len(batches) == len(plan['changed']), 'annotate every changed section exactly once')
        indexed = {s['key']: s for s in batches}
        require(len(indexed) == len(batches) and set(indexed) == {s['key'] for s in plan['changed']}, 'changed section keys mismatch')
        state = copy.deepcopy(_state(store))
        for section in plan['changed']:
            batch = indexed[section['key']]
            require(batch.get('sha256') == section['sha256'], 'section hash mismatch')
            _validate_items(batch.get('items'), section)
            state['sections'][section['key']] = {**section, 'items': batch['items'], 'removed': False}
        for key in plan['removed']:
            state['sections'][key]['removed'] = True
        if not plan['needs_analysis'] and state.get('document_sha256') == plan['document_sha256'] and state.get('baseline_data_sha256') == plan['baseline_data_sha256']:
            return {'changed': False, 'revision': state['revision']}
        old_revision = state.pop('revision')
        if old_revision:
            state['history'].append(old_revision)
        state.update(document_sha256=plan['document_sha256'], source_path=plan['source_path'],
                     workspace_relative=os.path.relpath(workspace, store).replace('\\', '/'),
                     baseline_report_sha256=plan['baseline_report_sha256'], baseline_data_sha256=plan['baseline_data_sha256'])
        if refresh:
            state['last_correction_reason'] = annotations['correction_reason']
        raw = (json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
        revision = digest(raw)
        snapshot = _inside(store, store / 'snapshots' / (revision + '.json'))
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.exists():
            require(snapshot.read_bytes() == raw, 'snapshot collision')
        else:
            with snapshot.open('xb') as handle:
                handle.write(raw)
        _write_json(store / 'state.json', {**state, 'revision': revision})
        return {'changed': True, 'revision': revision, 'sections_analyzed': len(batches)}
    finally:
        lock.unlink(missing_ok=True)


def load_progress(store):
    store = Path(store).resolve()
    state = _state(store)
    require(state['revision'] is not None, 'progress ledger has not been initialized')
    # Source reads are limited to the original configured workspace notes document.
    workspace = (store / state['workspace_relative']).resolve()
    require(store.is_relative_to(workspace) and store != workspace, 'invalid workspace binding')
    source = _inside(workspace, workspace / state['source_path'])
    try:
        current_sha, current = _sections(source)
        source_error = None
    except (OSError, ValueError) as exc:
        current_sha, current, source_error = None, {}, str(exc)
    items = []
    for key, section in state['sections'].items():
        stale = source_error or section.get('removed') or current.get(key, {}).get('sha256') != section['sha256']
        for item in section['items']:
            items.append({**item, 'source_key': key,
                          'source': {'path': state['source_path'], 'line': current.get(key, section)['line'], 'sha256': section['sha256']},
                          'evidence_state': 'STALE' if stale else 'DOCUMENT_ONLY',
                          'source_state': 'REMOVED' if section.get('removed') else 'CHANGED' if stale else 'CURRENT'})
    return {'schema_version': '1.0.0', 'revision': state['revision'], 'baseline_report_sha256': state['baseline_report_sha256'],
            'baseline_data_sha256': state.get('baseline_data_sha256'),
            'source_path': state['source_path'], 'document_sha256': state['document_sha256'],
            'needs_sync': current_sha != state['document_sha256'], 'source_error': source_error,
            'items': items, 'history': state['history']}


def bind_progress(progress, records):
    result = copy.deepcopy(progress)
    for item in result['items']:
        item['matched_test_ids'] = []
        item['unmatched_targets'] = []
        item['ambiguous_targets'] = []
        for target in item['targets']:
            hits = [r['id'] for r in records.values() if (r['repo'], r['path'], r['name']) ==
                    (target['project'], target['path'], target['name'])]
            if len(hits) == 1:
                item['matched_test_ids'].extend(hits)
            elif not hits:
                item['unmatched_targets'].append(target)
            else:
                item['ambiguous_targets'].append(target)
    return result


def _for_report(report, store=None):
    _, sha, view, records = _read_report(report)
    data = load_progress(store) if store else copy.deepcopy(view.get('progress'))
    if data is None:
        return None
    require(data['baseline_report_sha256'] == view['meta'].get('baseline_report_sha256', sha), 'progress belongs to a different report snapshot')
    require(data.get('baseline_data_sha256') == _content_binding(view), 'baseline report inventory/evidence has changed; re-sync older ledgers from the preserved baseline')
    data['freshness'] = 'LIVE_NOTES_CHECK' if store else 'EMBEDDED_SNAPSHOT'
    return bind_progress(data, records)


def get_ut_context(report_path, ut_name=None, *, file_path=None, project=None, path=None,
                   test_id=None, progress_path=None, detail=False, project_root=None, limit=30):
    require(not file_path or not (ut_name or test_id), 'choose a file or a test name/ID')
    baseline = (get_ut_cards(report_path, file_path, project=project, project_root=project_root)
                if file_path else get_ut_card(report_path, ut_name, project=project, path=path, test_id=test_id, limit=limit))
    progress = _for_report(report_path, progress_path)
    if progress:
        query_file = baseline['query'].get('file_path') if file_path else str(path).replace('\\', '/').removeprefix('./') if path is not None else None
        selected_ids = {t['id'] for c in baseline.get('candidates', []) for t in c['matched_tests']}
        for card in baseline.get('cards', []) + ([baseline['card']] if 'card' in baseline else []):
            selected_ids.update(card['matched_test_ids'])
        def selected(item):
            if selected_ids.intersection(item['matched_test_ids']):
                return True
            if test_id:
                return False
            return any((project is None or t['project'] == project) and
                       (query_file is None or t['path'] == query_file) and
                       (ut_name is None or _name_matches(t['name'], ut_name, 'exact')) for t in item['targets'])
        progress['items'] = [i for i in progress['items'] if selected(i)]
        progress['item_count'] = len(progress['items'])
        progress['status'] = 'FOUND' if progress['items'] else 'UNRECORDED'
        if not detail:
            progress.pop('history', None)
            for item in progress['items']:
                item.pop('quote', None)
    return {'baseline': baseline if detail else summarize_result(baseline), 'progress': progress,
            'sync_state': 'PROGRESS_AVAILABLE' if progress and progress['items'] else 'BASELINE_ONLY'}


def render_progress_report(report, store, output, *, replace=False):
    report = Path(report).resolve()
    output = Path(output).resolve()
    require(output != report, 'create a new report; preserve the archived baseline')
    require(replace or not output.exists(), 'output exists; use explicit replacement')
    _, sha, view, _ = _read_report(report)
    view['progress'] = _for_report(report, store)
    view['meta']['baseline_report_sha256'] = view['meta'].get('baseline_report_sha256', sha)
    from . import __version__, TEMPLATE_VERSION
    view['meta']['presentation'] = {'skill_version': __version__, 'template_version': TEMPLATE_VERSION}
    view['meta']['capabilities'] = sorted(set(view['meta'].get('capabilities', [])) | {'ut-card-deep-link-v1', 'ut-progress-v1'})
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent, delete=False) as handle:
        handle.write(view_html(view))
        temporary = Path(handle.name)
    try:
        validate_html(temporary)
        if replace:
            os.replace(temporary, output)
        else:
            os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output
