import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ut_diff_report.discovery import ResolutionError, resolve_project, scan_python
from ut_diff_report.execution import run_unittest

ROOT = Path(__file__).resolve().parents[1]


class ToolTests(unittest.TestCase):
    def test_distribution_omits_private_report_and_evidence_under_docs(self):
        spec = importlib.util.spec_from_file_location('installer_private', ROOT / 'scripts/install_skill.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'docs/ut-diff/run').mkdir(parents=True)
            (source / 'docs/ut_result.html').write_text('private synthetic report', encoding='utf-8')
            (source / 'docs/ut-diff/run/input.json').write_text('{}', encoding='utf-8')
            (source / 'docs/usage.md').write_text('public documentation', encoding='utf-8')
            files = [p.relative_to(source).as_posix() for p in module.distribution_files(source)]
            self.assertEqual(files, ['docs/usage.md'])

    def test_resolution_is_bounded_and_ambiguous(self):
        with tempfile.TemporaryDirectory() as directory:
            w = Path(directory)
            for sub in ('one/service', 'two/service'):
                (w / sub).mkdir(parents=True)
            with self.assertRaises(ResolutionError) as ctx:
                resolve_project('service', w)
            self.assertEqual(len(ctx.exception.candidates), 2)
            self.assertEqual(resolve_project('one/service', w), (w / 'one/service').resolve())
            with self.assertRaises(ResolutionError):
                resolve_project('no-such-project', w)

    def test_python_inventory_and_real_subtests_not_double_counted(self):
        project = ROOT / 'tests/fixtures/blue'
        inventory = scan_python(project, 'A')
        self.assertEqual(len(inventory['tests']), 3)
        self.assertEqual(sum(len(t['subtests']) for t in inventory['tests']), 1)
        with tempfile.TemporaryDirectory() as directory:
            result = run_unittest(project, Path(directory))
            self.assertEqual(len(result['tests']), 3)
            self.assertEqual({x['status'] for x in result['tests']}, {'PASS'})
            self.assertEqual(sum(len(t['children']) for t in result['tests']), 3)
            self.assertTrue(result['command'])

    def test_ast_scan_does_not_import_and_captures_pytest_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / 'test_demo.py').write_text('''import pytest
raise RuntimeError("must not import")
@pytest.mark.parametrize("amount", [0, -1])
def test_reject(amount):
    assert amount <= 0
''', encoding='utf-8')
            inv = scan_python(project, 'A')
            self.assertEqual(len(inv['tests']), 1)
            self.assertEqual(len(inv['tests'][0]['parameters']), 1)
            self.assertFalse(inv['errors'])

    def test_installer_copy_is_idempotent_and_collision_safe(self):
        spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install_skill.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            dest = module.install(ROOT, Path(directory), 'copy')
            self.assertEqual(dest.name, 'ut-analysis')
            self.assertTrue((dest / 'SKILL.md').is_file())
            self.assertFalse((dest / '.git').exists())
            self.assertEqual(module.install(ROOT, Path(directory), 'copy'), dest)
            (dest / 'SKILL.md').write_text('unrelated', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                module.install(ROOT, Path(directory), 'copy')

    def test_link_install_with_spaces(self):
        spec = importlib.util.spec_from_file_location('installer_link', ROOT / 'scripts/install_skill.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'source with spaces'
            source.mkdir()
            (source / 'SKILL.md').write_text('synthetic skill', encoding='utf-8')
            target = module.install(source, root / 'skills with spaces', 'link')
            try:
                self.assertEqual(target.resolve(), source)
                self.assertEqual(module.install(source, root / 'skills with spaces', 'link'), target)
            finally:
                self.assertTrue(target.absolute().is_relative_to(root))
                if os.name == 'nt':
                    target.rmdir()
                else:
                    target.unlink()

    def test_copy_install_renders_from_another_workspace(self):
        spec = importlib.util.spec_from_file_location('installer_copy', ROOT / 'scripts/install_skill.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = module.install(ROOT, root / 'skills', 'copy')
            workspace = root / 'independent workspace'
            workspace.mkdir()
            process = subprocess.run([sys.executable, str(target / 'scripts/render_report.py'),
                                      str(target / 'examples/sample_input.json')], cwd=workspace,
                                     capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue((workspace / 'docs/ut_result.html').is_file())
            self.assertFalse((target / 'docs/ut_result.html').exists())


if __name__ == '__main__':
    unittest.main()
