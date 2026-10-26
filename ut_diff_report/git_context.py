"""Read current worktrees or create owned, detached branch snapshots without checkout in user trees."""

import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile


class GitSelectionError(ValueError):
    pass


def git(root, *args, check=True):
    result = subprocess.run(['git', '-C', str(root), *map(str, args)], capture_output=True)
    if check and result.returncode:
        raise GitSelectionError(result.stderr.decode('utf-8', errors='replace').strip())
    return result


def output(root, *args, check=True):
    return git(root, *args, check=check).stdout.decode('utf-8', errors='replace').strip()


def snapshot(root):
    """Hash tracked and non-ignored untracked bytes; never follow source symlinks."""
    paths = git(root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').stdout.split(b'\0')
    digest = hashlib.sha256()
    for name in sorted(set(p for p in paths if p)):
        path = Path(root) / os.fsdecode(name)
        digest.update(name + b'\0')
        if path.is_symlink():
            digest.update(b'link:' + os.fsencode(os.readlink(path)))
        elif path.is_file():
            with path.open('rb') as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(block)
        else:
            digest.update(b'<missing-or-submodule>')
        digest.update(b'\0')
    return digest.hexdigest()


def inspect(project):
    project = Path(project).resolve()
    if not project.is_dir():
        raise GitSelectionError('project directory does not exist: ' + str(project))
    try:
        probe = git(project, 'rev-parse', '--show-toplevel', check=False)
    except FileNotFoundError:
        return {'is_git': False, 'git_available': False, 'repository_root': None, 'analysis_root': str(project),
                'branch': 'Git 未安装', 'sha': None, 'detached': False,
                'has_uncommitted_changes': None, 'snapshot_digest': None}
    if probe.returncode:
        return {'is_git': False, 'repository_root': None, 'analysis_root': str(project),
                'branch': '非 Git 项目', 'sha': None, 'detached': False,
                'has_uncommitted_changes': False, 'snapshot_digest': None}
    root = Path(probe.stdout.decode('utf-8').strip()).resolve()
    branch = output(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', check=False)
    sha = output(root, 'rev-parse', '--verify', 'HEAD', check=False) or None
    status = git(root, 'status', '--porcelain=v1', '-z').stdout
    from .execution import source_digest
    scope_digest = source_digest(project)
    tracked_scope = git(project, 'ls-files', '--cached', '--', '.').stdout
    ignored_scope_source = not tracked_scope and scope_digest != hashlib.sha256().hexdigest()
    combined = hashlib.sha256(((sha or '<unborn>') + ':' + scope_digest).encode()).hexdigest()
    return {'is_git': True, 'repository_root': str(root), 'analysis_root': str(project),
            'branch': branch or 'detached HEAD', 'sha': sha, 'detached': not bool(branch) and bool(sha),
            'has_uncommitted_changes': bool(status) or ignored_scope_source, 'snapshot_digest': combined,
            'analysis_scope_untracked_or_ignored': bool(ignored_scope_source), 'scope_source_digest': scope_digest,
            'repository_snapshot_digest': snapshot(root),
            'status_digest': hashlib.sha256(status).hexdigest(),
            'status': status.decode('utf-8', errors='replace').replace('\0', '\n').strip(),
            'unborn_head': sha is None}


def resolve_branch(root, branch):
    """Only actual local/remote branch refs. No tags, revision expressions or implicit fetch."""
    if not branch or branch.startswith('-') or any(c in branch for c in ('\0', '\n', '\r')):
        raise GitSelectionError('invalid branch name')
    local = branch if branch.startswith('refs/heads/') else 'refs/heads/' + branch
    if git(root, 'show-ref', '--verify', '--quiet', local, check=False).returncode == 0:
        return local
    remote = branch if branch.startswith('refs/remotes/') else 'refs/remotes/' + branch
    if git(root, 'show-ref', '--verify', '--quiet', remote, check=False).returncode == 0:
        return remote
    refs = output(root, 'for-each-ref', '--format=%(refname)', 'refs/remotes/').splitlines()
    candidates = [r for r in refs if r.removeprefix('refs/remotes/').split('/', 1)[-1] == branch
                  and not r.endswith('/HEAD')]
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise GitSelectionError('ambiguous remote-tracking branch: ' + ', '.join(candidates))
    raise GitSelectionError('branch not found in local/existing remote-tracking refs: ' + branch + '; no fetch performed')


def prepare(project, project_id, branch=None):
    original = inspect(project)
    original.update(project_id=project_id, requested_branch=branch, owned_worktree=False,
                    source_has_uncommitted_changes=original['has_uncommitted_changes'],
                    selection='working_tree', remote_status='not fetched; existing local refs only')
    if branch is None:
        return original
    if not original['is_git']:
        raise GitSelectionError('explicit branch requires a Git repository')
    root = Path(original['repository_root'])
    ref = resolve_branch(root, branch)
    sha = output(root, 'rev-parse', '--verify', ref + '^{commit}')
    relative = Path(project).resolve().relative_to(root)
    parent = Path(tempfile.mkdtemp(prefix='ut-diff-worktrees-')).resolve()
    worktree = parent / 'analysis'
    hooks = parent / 'empty-hooks'
    hooks.mkdir()
    token = secrets.token_hex(16)
    marker = {'token': token, 'repository_root': str(root), 'worktree_root': str(worktree), 'sha': sha}
    (parent / '.ut-diff-owner.json').write_text(json.dumps(marker), encoding='utf-8')
    try:
        # Disable hooks for this operation only; never change repository/global configuration.
        git(root, '-c', 'core.hooksPath=' + str(hooks), 'worktree', 'add', '--detach', str(worktree), sha)
    except GitSelectionError as exc:
        # Preserve the owned marker/path if Git left partial resources; never switch/fallback.
        raise GitSelectionError(f'isolated checkout failed: {exc}; owned resource retained at {parent}') from exc
    analysis = worktree / relative
    if not analysis.is_dir():
        ctx = {**original, **marker, 'owner_token': token, 'owned_worktree': True, 'temporary_parent': str(parent)}
        cleanup(ctx)
        raise GitSelectionError('selected branch does not contain the requested project subdirectory')
    selected = inspect(analysis)
    return {**selected, 'project_id': project_id, 'source_root': str(Path(project).resolve()),
            'source_repository_root': str(root), 'source_has_uncommitted_changes': original['has_uncommitted_changes'],
            'source_branch': original['branch'], 'source_sha': original['sha'],
            'source_status_digest': original.get('status_digest'),
            'branch': ref.removeprefix('refs/heads/').removeprefix('refs/remotes/'),
            'requested_branch': branch, 'resolved_ref': ref, 'selection': 'branch_worktree',
            'remote_status': 'not fetched; existing local remote-tracking refs only',
            'owned_worktree': True, 'temporary_parent': str(parent), 'worktree_root': str(worktree),
            'owner_token': token, 'detached': True, 'sha': sha}


def cleanup(context):
    if not context.get('owned_worktree'):
        return 'not owned; left untouched'
    parent = Path(context['temporary_parent']).resolve()
    marker_path = parent / '.ut-diff-owner.json'
    if not parent.name.startswith('ut-diff-worktrees-') or not marker_path.is_file():
        raise GitSelectionError('refusing cleanup: no owned resource marker')
    marker = json.loads(marker_path.read_text(encoding='utf-8'))
    worktree = Path(context.get('worktree_root', context.get('analysis_root', ''))).resolve()
    if (worktree != parent / 'analysis' or marker['worktree_root'] != str(worktree)
            or marker['token'] != context.get('owner_token') or marker['sha'] != context.get('sha')):
        raise GitSelectionError('refusing cleanup: ownership/path/commit mismatch')
    root = Path(marker['repository_root']).resolve()
    current = inspect(worktree)
    if not current['is_git'] or current['sha'] != marker['sha'] or current['has_uncommitted_changes']:
        raise GitSelectionError('owned worktree changed or is dirty; retained for inspection: ' + str(worktree))
    registered = output(root, 'worktree', 'list', '--porcelain')
    registered_paths = {str(Path(line[9:]).resolve()) for line in registered.splitlines() if line.startswith('worktree ')}
    if str(worktree) not in registered_paths:
        raise GitSelectionError('worktree is not registered with the original repository')
    git(root, 'worktree', 'remove', str(worktree))  # no force, no prune, no other worktree deletion
    marker_path.unlink()
    (parent / 'empty-hooks').rmdir()
    parent.rmdir()
    return 'removed owned clean worktree'
