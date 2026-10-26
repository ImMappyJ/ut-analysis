"""Read UT cards from an existing offline report without executing JavaScript or tests."""
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from urllib.parse import quote

from .core import ReportParser, index_unique, require


def _read_report(report_path):
    path = Path(report_path).expanduser().resolve()
    raw = path.read_bytes()
    parser = ReportParser()
    parser.feed(raw.decode('utf-8-sig'))
    require(len(parser.payloads) == 1, 'unsupported report: expected one application/json script with id=ut-data')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate embedded JSON key: ' + key)
            result[key] = value
        return result

    view = json.loads(parser.payloads[0], object_pairs_hook=unique,
                      parse_constant=lambda value: require(False, 'invalid JSON constant: ' + value))
    require(isinstance(view, dict), 'unsupported report data')
    require(isinstance(view.get('meta'), dict) and isinstance(view.get('records'), list)
            and isinstance(view.get('pairs'), list), 'unsupported report: no recognized card inventory')
    records = index_unique(view['records'], 'report UT records')
    pairs = index_unique(view['pairs'], 'report comparison rows')
    seen = set()
    for record in records.values():
        require(record.get('repo') in ('A', 'B') and all(isinstance(record.get(k), str) for k in ('id', 'name', 'path')),
                'invalid UT card identity')
        require(isinstance(record.get('result'), dict), 'invalid UT card execution evidence')
    for pair in pairs.values():
        for side, pid in (('a', 'A'), ('b', 'B')):
            tid = pair.get(side)
            if tid is not None:
                require(tid in records and records[tid]['repo'] == pid and tid not in seen,
                        'invalid/duplicate UT reference in report comparison rows')
                seen.add(tid)
    mode = view['meta'].get('mode', 'compare')
    require(mode in ('compare', 'audit', 'full'), 'unsupported report mode')
    require((not pairs and all(r['repo'] == 'A' for r in records.values())) if mode == 'audit'
            else seen == set(records), 'report card inventory does not agree with its analysis mode')
    return path, hashlib.sha256(raw).hexdigest(), view, records


def _name_matches(name, query, match):
    if match == 'contains':
        return query.casefold() in name.casefold()
    return name == query or re.split(r'::|\.', name)[-1] == query


def get_ut_card(report_path, ut_name=None, *, project=None, path=None, test_id=None, match='exact', limit=30, detail=True):
    """Return one original card or ambiguity candidates for a UT name/ID."""
    result = _query_cards(report_path, ut_name, project=project, path=path, test_id=test_id, match=match, limit=limit)
    return result if detail else summarize_result(result)


def _file_path(path, project_root):
    require(isinstance(path, (str, Path)) and bool(str(path).strip()), 'provide a nonempty test file path')
    text = str(path).replace('\\', '/')
    require('..' not in text.split('/'), 'test file path must not contain parent traversal')
    cls = PureWindowsPath if PureWindowsPath(text).drive else PurePosixPath
    value = cls(text)
    require(not value.drive or value.is_absolute(), 'drive-relative test paths are unsupported')
    if value.is_absolute():
        require(project_root is not None, 'absolute test path requires explicit project_root (--project-root)')
        root_text = str(project_root).replace('\\', '/')
        require('..' not in root_text.split('/'), 'project_root must not contain parent traversal')
        root = cls(root_text)
        require(root.is_absolute(), 'project_root must be absolute')
        try:
            value = value.relative_to(root)
        except ValueError:
            require(False, 'test file path must be inside project_root')
    else:
        require(project_root is None, 'project_root is only used with absolute test paths')
    result = value.as_posix()
    require(result != '.', 'provide a test file path, not the project root')
    return result


def get_ut_cards(report_path, file_path, *, project=None, project_root=None, detail=True):
    """Return every distinct card touching an exact file path, without truncation.

    Absolute paths require an explicit project root; resolution is lexical and never
    reads the source tree. The opposite side is retained even if its path differs.
    """
    path = _file_path(file_path, project_root)
    result = _query_cards(report_path, project=project, path=path, many=True)
    return result if detail else summarize_result(result)


def summarize_result(result):
    """Keep identities, goals and result states; omit code, diffs and raw logs."""
    def brief(card):
        out = {k: v for k, v in card.items() if k not in ('left', 'right', 'relation', 'quality', 'matched_instances')}
        for side in ('left', 'right'):
            record = card[side]
            if record is None:
                out[side] = None
                continue
            out[side] = {k: record.get(k) for k in ('id', 'repo', 'name', 'path', 'line', 'module', 'owner', 'priority', 'goal')}
            out[side]['result'] = {k: record['result'].get(k) for k in ('status', 'elapsed', 'reason', 'startedAt', 'cached')}
            out[side]['assertion_count'] = len(record.get('assertions', []))
        out['relation'] = ({k: card['relation'].get(k) for k in ('id', 'match', 'execution', 'executionNote')}
                           if card['relation'] else None)
        out['quality_counts'] = {k: len(v) for k, v in card['quality'].items()}
        return out
    out = dict(result)
    if 'card' in out:
        out['card'] = brief(out['card'])
    if 'cards' in out:
        out['cards'] = [brief(c) for c in out['cards']]
    out['detail_level'] = 'summary'
    return out


def _query_cards(report_path, ut_name=None, *, project=None, path=None, test_id=None, match='exact', limit=30, many=False):
    """Return FOUND + one full card, AMBIGUOUS + candidates, or NOT_FOUND.

    Two hits in the same comparison row are one card. Observed runtime instance hits return
    their parent card. Archived matching, execution and quality judgments are not recomputed.
    """
    require(many or bool(ut_name) or bool(test_id), 'provide a nonempty UT name or test ID')
    require(project in (None, 'A', 'B'), 'project must be A or B')
    require(match in ('exact', 'contains'), 'match must be exact or contains')
    require(type(limit) is int and 1 <= limit <= 200, 'limit must be between 1 and 200')
    if ut_name is not None:
        require(isinstance(ut_name, str) and bool(ut_name.strip()), 'UT name must be nonempty text')
    report, digest, view, records = _read_report(report_path)
    normalize = lambda value: str(value).replace('\\', '/').removeprefix('./')
    hits = {}
    for record in records.values():
        if project and record['repo'] != project or test_id and record['id'] != test_id:
            continue
        if path is not None and normalize(record['path']) != normalize(path):
            continue
        children = [c for c in record['result'].get('children', []) if ut_name and
                    isinstance(c.get('name'), str) and _name_matches(c['name'], ut_name, match)]
        if not ut_name or _name_matches(record['name'], ut_name, match) or children:
            hits[record['id']] = children
    rows = view['pairs'] if view['meta'].get('mode') != 'audit' else [
        {'id': 'ut-single-' + r['id'], 'a': r['id'], 'b': None} for r in records.values()]
    matched = [row for row in rows if row.get('a') in hits or row.get('b') in hits]
    source = {'report_path': str(report), 'sha256': digest, 'run_id': view['meta'].get('run_id'),
              'generated_at': view['meta'].get('generated_at'), 'mode': view['meta'].get('mode', 'compare'),
              'skill_version': view['meta'].get('skillVersion'), 'template_version': view['meta'].get('templateVersion')}
    supports_link = 'ut-card-deep-link-v1' in view['meta'].get('capabilities', [])
    candidates = []
    for row in (matched if many else matched[:limit]):
        selected = [records[tid] for tid in (row.get('a'), row.get('b')) if tid in hits]
        fragment = 'ut-card=' + quote(selected[0]['id'], safe='')
        candidates.append({'card_id': row['id'], 'matched_tests': [
            {key: r.get(key) for key in ('id', 'repo', 'name', 'path', 'line')} for r in selected],
            'locator': {'supported': supports_link, 'report_path': str(report),
                        'url': report.as_uri() + '#' + fragment if supports_link else None,
                        'fragment': fragment if supports_link else None,
                        'reason': '' if supports_link else 'Older report template has no automatic card deep link; use returned card data or the report search.'}})
    result = {'query': {'name': ut_name, 'project': project, 'path': path, 'test_id': test_id, 'match': match},
              'status': 'FOUND' if len(matched) == 1 else 'AMBIGUOUS' if matched else 'NOT_FOUND',
              'source': source, 'candidate_count': len(matched), 'candidates': candidates,
              'truncated': len(matched) > limit}
    cards = []
    for row in (matched if many else matched[:1] if len(matched) == 1 else []):
        tids = {tid for tid in (row.get('a'), row.get('b')) if tid is not None}
        quality = view.get('quality', {})
        traces = [t for t in quality.get('traces', []) if tids & set(t['test_ids'])]
        issues = [i for i in quality.get('issues', []) if tids & set(i['test_ids'])]
        rids = {t['requirement_id'] for t in traces} | {rid for i in issues for rid in i['requirement_ids']}
        card = {'id': row['id'], 'kind': 'audit' if source['mode'] == 'audit' else 'comparison',
            'left': records.get(row.get('a')), 'right': records.get(row.get('b')),
            'relation': None if source['mode'] == 'audit' else row,
            'matched_test_ids': [tid for tid in (row.get('a'), row.get('b')) if tid in hits],
            'matched_instances': [{'test_id': tid, **c} for tid in (row.get('a'), row.get('b')) for c in hits.get(tid, [])],
            'quality': {'traces': traces, 'issues': issues,
                        'requirements': [r for r in quality.get('requirements', []) if r['id'] in rids],
                        'sources': [s for s in quality.get('sources', []) if any(
                            s['id'] in r['source_ids'] for r in quality.get('requirements', []) if r['id'] in rids)]}}
        cards.append(card)
    if many:
        for card, candidate in zip(cards, candidates):
            card['locator'] = candidate['locator']
        return {'query': {'file_path': path, 'project': project},
                'status': 'FOUND' if cards else 'NOT_FOUND', 'source': source,
                'card_count': len(cards), 'matched_test_count': len(hits),
                'cards': cards, 'truncated': False}
    if cards:
        result['card'] = cards[0]
    return result
