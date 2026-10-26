"""Bounded project resolution and import-free Python AST inventory."""

import ast
import hashlib
import json
from pathlib import Path
import re

IGNORED = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', 'vendor',
           '.artifacts', '.local', 'dist', 'build', '.tox'}


def select_mode(mode='auto', *, project_b=None, branch_b=None):
    """Choose single-project audit or preserve an explicit two-project intent."""
    if mode not in ('auto', 'audit', 'compare', 'full'):
        raise ValueError('mode must be auto, audit, compare or full')
    selected = ('compare' if project_b else 'audit') if mode == 'auto' else mode
    if branch_b and not project_b:
        raise ValueError('project B branch requires project B')
    if selected == 'audit' and project_b:
        raise ValueError('audit accepts one project only')
    if selected in ('compare', 'full') and not project_b:
        raise ValueError('compare/full require project B; no silent fallback to audit')
    return selected


class ResolutionError(ValueError):
    def __init__(self, message, candidates=()):
        self.candidates = [str(p) for p in candidates]
        super().__init__(message + (': ' + ', '.join(self.candidates) if candidates else ''))


def project_dirs(workspace, depth=4):
    """Only bounded workspace children; do not traverse directory links."""
    workspace = Path(workspace).resolve()
    yield workspace
    level = [workspace]
    for _ in range(depth):
        next_level = []
        for parent in level:
            try:
                children = sorted(parent.iterdir(), key=lambda p: p.name.casefold())
            except OSError:
                continue
            for child in children:
                if not child.is_dir() or child.name in IGNORED or child.is_symlink():
                    continue
                resolved = child.resolve()
                if not resolved.is_relative_to(workspace):
                    continue
                yield resolved
                next_level.append(resolved)
        level = next_level


def resolve_project(value, workspace):
    workspace = Path(workspace).resolve()
    given = Path(value).expanduser()
    direct = given if given.is_absolute() else workspace / given
    if direct.is_dir():
        return direct.resolve()
    dirs = list(project_dirs(workspace))
    exact = [d for d in dirs if d.name.casefold() == value.casefold()]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ResolutionError('ambiguous project; ask user to select', exact)
    named = []
    for directory in dirs:
        names = set()
        try:
            p = directory / 'package.json'
            if p.is_file():
                names.add(json.loads(p.read_text(encoding='utf-8')).get('name', ''))
            p = directory / 'go.mod'
            if p.is_file():
                match = re.search(r'^module\s+(.+)', p.read_text(encoding='utf-8'), re.M)
                if match:
                    names.add(match[1].strip())
            p = directory / 'pyproject.toml'
            if p.is_file():
                # Read only unambiguous [project] name; no dependency on Python 3.11 tomllib.
                block = re.search(r'^\[project\]\s*$(.*?)(?=^\[|\Z)', p.read_text(encoding='utf-8'), re.M | re.S)
                if block:
                    match = re.search(r'^name\s*=\s*[\'"]([^\'"]+)', block[1], re.M)
                    if match:
                        names.add(match[1])
        except (OSError, ValueError):
            continue
        if value in names:
            named.append(directory)
    if len(named) == 1:
        return named[0]
    raise ResolutionError('ambiguous project; ask user to select' if named else 'project not found in workspace', named)


def stable_id(project_id, path, locator):
    return project_id + '-' + hashlib.sha256((path + '\0' + locator).encode()).hexdigest()[:20]


def scan_python(root, project_id):
    root = Path(root).resolve()
    tests, errors, files = [], [], []
    for path in sorted(root.rglob('*.py')):
        relative = path.relative_to(root)
        if set(relative.parts) & IGNORED or path.is_symlink() or not path.resolve().is_relative_to(root):
            continue
        if not (path.name.startswith('test_') or path.name.endswith('_test.py')):
            continue
        name = relative.as_posix()
        files.append(name)
        try:
            import tokenize
            with tokenize.open(path) as handle:
                source = handle.read()
            tree = ast.parse(source, filename=name)
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append({'path': name, 'error': str(exc)})
            continue
        lines = source.splitlines()
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith('test'):
                continue
            parent = parents.get(node)
            # Nested helpers and methods of helper classes are not pytest/unittest entries.
            if not isinstance(parent, (ast.Module, ast.ClassDef)):
                continue
            suite = parent.name if isinstance(parent, ast.ClassDef) else ''
            if isinstance(parent, ast.ClassDef):
                bases = [ast.unparse(b) for b in parent.bases]
                if not (parent.name.startswith('Test') or any('TestCase' in b for b in bases)):
                    continue
            locator = (suite + '.' if suite else '') + node.name
            calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
            assertions = [{'code': ast.get_source_segment(source, n) or ast.unparse(n), 'line': n.lineno,
                           'method': 'assert' if isinstance(n, ast.Assert) else ast.unparse(n.func)}
                          for n in ast.walk(node) if isinstance(n, ast.Assert) or
                          isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and
                          (n.func.attr.startswith('assert') or n.func.attr in ('fail', 'raises'))]
            subs = [{'name': ast.unparse(n), 'expression': ast.unparse(n), 'line': n.lineno,
                     'code': ast.get_source_segment(source, n) or ast.unparse(n)} for n in calls
                    if isinstance(n.func, ast.Attribute) and n.func.attr == 'subTest']
            params = [{'line': d.lineno, 'code': ast.unparse(d)} for d in node.decorator_list
                      if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == 'parametrize']
            decorators = [ast.unparse(d) for d in node.decorator_list]
            classification = 'e2e' if any('e2e' in d for d in decorators + list(relative.parts)) else 'integration' if any('integration' in d for d in decorators + list(relative.parts)) else 'unit-candidate'
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            tests.append({'id': stable_id(project_id, name, locator), 'project_id': project_id,
                'name': locator, 'path': name, 'line': start, 'end_line': node.end_lineno,
                'suite': suite, 'kind_candidate': classification, 'code': '\n'.join(lines[start - 1:node.end_lineno]),
                'assertions': assertions, 'subtests': subs, 'parameters': params,
                'source_digest': hashlib.sha256(source.encode()).hexdigest()})
    return {'project_id': project_id, 'root': str(root), 'scanner': 'python-ast', 'files': files,
            'tests': tests, 'errors': errors, 'limitations': [
                '静态候选不等于框架收集结果；继承、动态生成、插件和自定义发现规则必须与原生 collection 核对。',
                '参数装饰器和 subTest 调用点不是已运行实例；必须由原生执行记录补充。',
                'unit-candidate 必须由 Agent 依据外部依赖与断言确认 UT 范围。']}
