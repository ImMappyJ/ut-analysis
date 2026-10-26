from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from ut_diff_report.git_context import GitSelectionError, cleanup, prepare, inspect
from ut_diff_report.discovery import scan_python
from ut_diff_report.execution import run_unittest


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


@unittest.skipUnless(shutil.which('git'), 'Git unavailable')
class GitContextTests(unittest.TestCase):
    def test_analysis_fingerprint_includes_data_but_excludes_report_outputs(self):
        before = inspect(self.repo)
        output = self.repo / 'docs' / 'ut-diff'
        output.mkdir(parents=True)
        (output / 'contexts.json').write_text('{}', encoding='utf-8')
        (output.parent / 'ut_result.html').write_text('generated', encoding='utf-8')
        self.assertEqual(inspect(self.repo)['snapshot_digest'], before['snapshot_digest'])
        (self.repo / 'behavior.txt').write_text('changed input', encoding='utf-8')
        self.assertNotEqual(inspect(self.repo)['snapshot_digest'], before['snapshot_digest'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        git(self.repo, 'init', '-b', 'main')
        (self.repo / 'behavior.txt').write_text('main', encoding='utf-8')
        test_code = 'import unittest\nfrom pathlib import Path\nclass TestVersion(unittest.TestCase):\n    def test_version(self): self.assertEqual(Path("behavior.txt").read_text(), "main")\n'
        (self.repo / 'test_version.py').write_text(test_code, encoding='utf-8')
        git(self.repo, 'add', '.')
        git(self.repo, '-c', 'user.name=Synthetic', '-c', 'user.email=example@example.invalid', 'commit', '-m', 'synthetic main')
        git(self.repo, 'branch', 'feature/refactor')
        git(self.repo, 'checkout', 'feature/refactor')
        (self.repo / 'behavior.txt').write_text('feature', encoding='utf-8')
        (self.repo / 'test_version.py').write_text(test_code.replace('"main"', '"feature"') +
            '    def test_extra(self): self.assertEqual(2 + 3, 5)\n', encoding='utf-8')
        git(self.repo, 'add', '.')
        git(self.repo, '-c', 'user.name=Synthetic', '-c', 'user.email=example@example.invalid', 'commit', '-m', 'synthetic feature')
        git(self.repo, 'checkout', 'main')
        (self.repo / 'behavior.txt').write_text('uncommitted', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_default_preserves_dirty_current_worktree(self):
        ctx = prepare(self.repo, 'A')
        self.assertEqual(Path(ctx['analysis_root']), self.repo)
        self.assertEqual(ctx['branch'], 'main')
        self.assertTrue(ctx['has_uncommitted_changes'])
        self.assertFalse(ctx['owned_worktree'])
        cleanup(ctx)
        self.assertEqual((self.repo / 'behavior.txt').read_text(), 'uncommitted')

    def test_same_repository_two_branches_are_isolated_and_source_untouched(self):
        before = git(self.repo, 'status', '--porcelain')
        a, b = prepare(self.repo, 'A', 'main'), prepare(self.repo, 'B', 'feature/refactor')
        try:
            self.assertNotEqual(a['analysis_root'], b['analysis_root'])
            self.assertEqual((Path(a['analysis_root']) / 'behavior.txt').read_text(), 'main')
            self.assertEqual((Path(b['analysis_root']) / 'behavior.txt').read_text(), 'feature')
            self.assertFalse(a['has_uncommitted_changes'])
            self.assertTrue(a['source_has_uncommitted_changes'])
            self.assertEqual(git(self.repo, 'branch', '--show-current'), 'main')
            self.assertEqual(git(self.repo, 'status', '--porcelain'), before)
        finally:
            cleanup(a)
            cleanup(b)
        self.assertEqual(len(git(self.repo, 'worktree', 'list', '--porcelain').split('worktree ')) - 1, 1)

    def test_missing_branch_never_falls_back_and_detached_is_real(self):
        with self.assertRaises(GitSelectionError):
            prepare(self.repo, 'A', 'does-not-exist')
        git(self.repo, 'checkout', '--detach', 'HEAD')
        ctx = prepare(self.repo, 'A')
        self.assertTrue(ctx['detached'])
        self.assertEqual(ctx['branch'], 'detached HEAD')

    def test_existing_remote_refs_local_priority_and_no_fetch(self):
        sha = git(self.repo, 'rev-parse', 'feature/refactor')
        git(self.repo, 'update-ref', 'refs/remotes/origin/cached-feature', sha)
        ctx = prepare(self.repo, 'B', 'cached-feature')
        try:
            self.assertEqual(ctx['resolved_ref'], 'refs/remotes/origin/cached-feature')
            self.assertIn('not fetched', ctx['remote_status'])
        finally:
            cleanup(ctx)

    def test_cleanup_does_not_remove_dirty_or_unowned_worktrees(self):
        ctx = prepare(self.repo, 'A', 'main')
        (Path(ctx['analysis_root']) / 'new.txt').write_text('preserve', encoding='utf-8')
        with self.assertRaises(GitSelectionError):
            cleanup(ctx)
        (Path(ctx['analysis_root']) / 'new.txt').unlink()
        cleanup(ctx)
        with self.assertRaises(GitSelectionError):
            cleanup({'owned_worktree': True, 'analysis_root': str(self.repo), 'temporary_parent': str(self.root)})

    def test_scan_and_execution_come_from_selected_actual_versions(self):
        a, b = prepare(self.repo, 'A', 'main'), prepare(self.repo, 'B', 'feature/refactor')
        try:
            for context, expected in ((a, 1), (b, 2)):
                project = Path(context['analysis_root'])
                self.assertEqual(len(scan_python(project, context['project_id'])['tests']), expected)
                result = run_unittest(project, self.root / (context['project_id'] + '-run'))
                self.assertEqual(len(result['tests']), expected)
                self.assertEqual({t['status'] for t in result['tests']}, {'PASS'})
                self.assertEqual(result['source_context']['sha'], context['sha'])
                self.assertEqual(Path(result['source_context']['analysis_root']), project)
            self.assertEqual((self.repo / 'behavior.txt').read_text(), 'uncommitted')
        finally:
            cleanup(a)
            cleanup(b)

    def test_one_side_branch_and_existing_user_worktree_are_preserved(self):
        existing = self.root / 'existing-user-worktree'
        git(self.repo, 'worktree', 'add', '--detach', str(existing), 'main')
        try:
            for side in ('A', 'B'):
                a = prepare(self.repo, 'A', 'feature/refactor' if side == 'A' else None)
                b = prepare(self.repo, 'B', 'feature/refactor' if side == 'B' else None)
                cleanup(a)
                cleanup(b)
                self.assertTrue((existing / 'behavior.txt').is_file())
                self.assertEqual(git(self.repo, 'branch', '--show-current'), 'main')
        finally:
            git(self.repo, 'worktree', 'remove', str(existing))
