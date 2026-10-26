"""Read stored requirements, quality evidence and repair progress without running analysis."""
import copy

from .card_query import _read_report, _file_path, _name_matches, get_ut_card
from .core import require, index_unique
from .progress import _for_report


def _page(items, offset, limit, availability='AVAILABLE'):
    end = min(offset + limit, len(items))
    return {'availability': availability, 'status': 'FOUND' if items else 'NOT_FOUND',
            'total': len(items), 'offset': offset, 'returned': len(items[offset:end]),
            'next_offset': end if end < len(items) else None, 'items': items[offset:end]}


def get_report_context(report_path, *, section='all', ut_name=None, test_id=None, file_path=None,
                       path=None, project_root=None, project=None, module=None, requirement_id=None,
                       issue_id=None, progress_id=None, progress_path=None, detail=False, offset=0, limit=30):
    """Query archived evidence with exact selectors and independently paginated collections.

    Module is a stable report module ID. Names retain original card ambiguity semantics.
    Explicit progress_path checks the configured notes; embedded progress stays a snapshot.
    Quality assessments are project-wide archived conclusions, never a filtered reassessment.
    """
    require(section in ('all', 'requirements', 'quality', 'progress'), 'unknown context section')
    require(project in (None, 'A', 'B'), 'project must be A or B')
    require(type(limit) is int and 1 <= limit <= 200 and type(offset) is int and offset >= 0,
            'limit must be 1..200 and offset nonnegative')
    selectors = (ut_name, test_id, file_path, requirement_id, issue_id, progress_id)
    require(sum(v is not None for v in selectors) <= 1, 'choose one UT/file/requirement/issue/progress identity')
    require(all(v is None or isinstance(v, str) and v.strip() for v in (ut_name, test_id, requirement_id, issue_id, progress_id, module)),
            'selectors must be nonempty text')
    require(path is None or ut_name is not None or test_id is not None, 'path requires UT name/ID')
    require(project_root is None or file_path is not None, 'project_root requires file_path')
    require(progress_path is None or section in ('all', 'progress'), 'progress_path requires all/progress section')
    require(progress_id is None or section in ('all', 'progress'), 'progress_id requires all/progress section')
    report, sha, view, records = _read_report(report_path)
    projects = view['meta'].get('projects', {})
    selected_projects = [p for p in projects if project is None or p == project]
    source = {'report_path': str(report), 'sha256': sha, 'run_id': view['meta'].get('run_id'),
              'generated_at': view['meta'].get('generated_at'), 'mode': view['meta'].get('mode', 'compare'),
              'projects': {p: projects[p] for p in selected_projects}, 'evidence_scope': 'ARCHIVED_REPORT'}
    result = {'status': 'FOUND', 'source': source, 'detail_level': 'full' if detail else 'summary',
              'query': {'section':section, 'project':project, 'module':module, 'ut_name':ut_name,
                        'test_id':test_id, 'file_path':str(file_path) if file_path is not None else None,
                        'requirement_id':requirement_id, 'issue_id':issue_id, 'progress_id':progress_id}}
    result['modules'] = [{k:m.get(k) for k in ('id','name','priority')} for m in view.get('modules', [])
                         if module is None or m['id'] == module]
    eligible = {tid for tid, r in records.items() if r['repo'] in selected_projects and
                (module is None or r.get('moduleId') == module)}
    tids = set(eligible)
    normalized_file = _file_path(file_path, project_root) if file_path is not None else None
    normalized_path = _file_path(path, None) if path is not None else None
    if normalized_file is not None:
        tids &= {tid for tid, r in records.items() if r['path'].replace('\\', '/') == normalized_file}
    if ut_name is not None or test_id is not None:
        identity = get_ut_card(report, ut_name, test_id=test_id, project=project, path=normalized_path, detail=False)
        result['identity'] = identity
        if identity['status'] == 'AMBIGUOUS':
            result['status'] = 'AMBIGUOUS'
            return result
        tids &= set(identity.get('card', {}).get('matched_test_ids', []))

    q = view.get('quality')
    require(q is None or isinstance(q, dict), 'invalid quality context')
    q = q or {}
    for key in ('requirements', 'sources', 'traces', 'issues'):
        require(isinstance(q.get(key, []), list), 'invalid quality collection: ' + key)
    requirements = index_unique(q.get('requirements', []), 'requirements')
    sources = index_unique(q.get('sources', []), 'requirement sources')
    index_unique(q.get('issues', []), 'quality issues')
    reqs = [r for r in requirements.values() if (module is None or r['module_id'] == module) and
            set(r.get('applicable_projects', projects)).intersection(selected_projects)]
    traces = [t for t in q.get('traces', []) if t['project_id'] in selected_projects]
    issues = [i for i in q.get('issues', []) if i['project_id'] in selected_projects and
              (module is None or i.get('module_id') == module or eligible.intersection(i['test_ids']))]
    prog = _for_report(report, progress_path) if section in ('all', 'progress') else None
    if issue_id is not None:
        issues = [i for i in issues if i['id'] == issue_id]
        linked = {r for i in issues for r in i['requirement_ids']}
        reqs = [r for r in reqs if r['id'] in linked]
        tids &= {t for i in issues for t in i['test_ids']}
    elif requirement_id is not None:
        reqs = [r for r in reqs if r['id'] == requirement_id]
        rids = {r['id'] for r in reqs}
        issues = [i for i in issues if rids.intersection(i['requirement_ids'])]
        tids &= ({tid for t in traces if t['requirement_id'] in rids for tid in t['test_ids']} |
                 {tid for i in issues for tid in i['test_ids']})
    elif progress_id is not None:
        tids &= {tid for i in (prog or {}).get('items', []) if i['issue_id'] == progress_id for tid in i['matched_test_ids']}

    test_scoped = any(v is not None for v in (ut_name, test_id, file_path, progress_id))
    if test_scoped:
        issues = [i for i in issues if tids.intersection(i['test_ids'])]
        rids = ({t['requirement_id'] for t in traces if tids.intersection(t['test_ids'])} |
                {rid for i in issues for rid in i['requirement_ids']})
        reqs = [r for r in reqs if r['id'] in rids]
    entries = []
    for req in reqs:
        related = [copy.deepcopy(t) for t in traces if t['requirement_id'] == req['id']]
        evidence = [copy.deepcopy(sources[s]) for s in req['source_ids'] if s in sources]
        if not detail:
            for t in related:
                t.pop('assertion_evidence', None)
                t.pop('evidence', None)
            for s in evidence:
                s.pop('excerpt', None)
        entries.append({'requirement': copy.deepcopy(req), 'traces': related, 'sources': evidence,
                        'missing_source_ids': [s for s in req['source_ids'] if s not in sources]})
    want_quality = section in ('all', 'quality', 'requirements')
    availability = 'AVAILABLE' if q else 'NOT_AVAILABLE'
    result['requirements'] = _page(entries if want_quality else [], offset, limit,
                                    availability if want_quality else 'NOT_REQUESTED')
    evaluations = {}
    if section in ('all', 'quality'):
        for pid in selected_projects:
            evaluation = view.get('quality_evaluation', {}).get('projects', {}).get(pid)
            if evaluation is None:
                continue
            evaluation = copy.deepcopy(evaluation)
            # Issues have their own filtered/paginated collection below.
            evaluation.pop('issues', None)
            if not detail:
                evaluation.get('coverage', {}).pop('files', None)
            if module is not None:
                evaluation['module_metrics'] = {k:v for k,v in evaluation.get('module_metrics', {}).items() if k == module}
                evaluation['module_requirements'] = [v for v in evaluation.get('module_requirements', []) if v['module_id'] == module]
            evaluations[pid] = evaluation
    selected_issues = copy.deepcopy(issues) if section in ('all', 'quality') else []
    if not detail:
        for i in selected_issues:
            i.pop('evidence', None)
    result['quality'] = {'availability': availability if section in ('all','quality') else 'NOT_REQUESTED',
                         'scope':'PROJECT_WIDE_SNAPSHOT', 'projects':evaluations,
                         'issues':_page(selected_issues,offset,limit,availability)}

    items = []
    if prog is not None:
        for item in prog['items']:
            targets = [t for t in item['targets'] if t['project'] in selected_projects]
            if project is not None and not targets:
                continue
            if module is not None and not eligible.intersection(item['matched_test_ids']):
                continue  # no fabricated module association for unbound candidates
            if progress_id is not None and item['issue_id'] != progress_id:
                continue
            if any(v is not None for v in (ut_name, test_id, file_path, requirement_id, issue_id)):
                hit = bool(tids.intersection(item['matched_test_ids']))
                if ut_name is not None or file_path is not None:
                    hit |= any((ut_name is None or _name_matches(t['name'], ut_name, 'exact')) and
                               (normalized_file is None or t['path'] == normalized_file) and
                               (normalized_path is None or t['path'] == normalized_path) for t in targets)
                if not hit:
                    continue
            item = copy.deepcopy(item)
            if not detail:
                item.pop('quote', None)
                item.pop('timeline', None)
            items.append(item)
    result['progress'] = _page(items,offset,limit,'AVAILABLE' if prog is not None else
                               'NOT_AVAILABLE' if section in ('all','progress') else 'NOT_REQUESTED')
    if prog is not None:
        result['progress'].update({k:prog.get(k) for k in ('freshness','revision','document_sha256','source_path','needs_sync','source_error')})
    test_items = []
    for tid, record in records.items():
        if tid not in tids:
            continue
        if detail:
            test_items.append(copy.deepcopy(record))
        else:
            brief = {k:record.get(k) for k in ('id','repo','name','path','line','moduleId','module','owner','priority','goal')}
            brief['execution_status'] = record['result']['status']
            test_items.append(brief)
    result['tests'] = _page(test_items,offset,limit)
    available = (q if section in ('requirements','quality') else prog if section == 'progress' else True)
    found = (entries if section == 'requirements' else selected_issues or evaluations if section == 'quality'
             else items if section == 'progress' else entries or selected_issues or items or test_items)
    # A missing exact selector is not a hit merely because project-wide assessments are attached.
    if any(v is not None for v in selectors) and not (entries or selected_issues or items or test_items):
        found = False
    result['status'] = 'NOT_AVAILABLE' if not available else 'FOUND' if found else 'NOT_FOUND'
    return result


def get_requirements(report_path, **kwargs):
    return get_report_context(report_path, section='requirements', **kwargs)


def get_quality(report_path, **kwargs):
    return get_report_context(report_path, section='quality', **kwargs)


def get_repair_progress(report_path, **kwargs):
    return get_report_context(report_path, section='progress', **kwargs)
