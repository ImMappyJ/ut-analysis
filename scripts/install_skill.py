"""Link or copy an independent source checkout into a Codex Skill directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

RESOURCES = ('SKILL.md', 'agents', 'assets', 'scripts', 'references', 'ut_diff_report', 'examples',
             'docs', 'tests', 'README.md', 'README_EN.md', 'CHANGELOG.md', 'pyproject.toml', 'LICENSE')


def distribution_files(source):
    for resource in RESOURCES:
        path = source / resource
        if path.is_file():
            yield path
        elif path.is_dir():
            for p in sorted(path.rglob('*')):
                relative = p.relative_to(source)
                if relative.as_posix() == 'docs/ut_result.html' or relative.parts[:2] in (('docs', 'ut-diff'), ('docs', 'ut-progress')):
                    continue
                if p.is_file() and '__pycache__' not in relative.parts and p.suffix not in ('.pyc', '.log'):
                    yield p


def manifest(source):
    return {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in distribution_files(source)}


def install(source, skills_dir, mode='link'):
    source, skills_dir = Path(source).resolve(), Path(skills_dir).expanduser().resolve()
    target = skills_dir / 'ut-analysis'
    expected = manifest(source)
    if target.exists() or target.is_symlink():
        if target.resolve() == source:
            return target
        marker = target / '.installation.json'
        if mode == 'copy' and marker.is_file():
            previous = json.loads(marker.read_text(encoding='utf-8'))
            if previous.get('source') == str(source) and previous.get('files') == expected and manifest(target) == expected:
                return target
        raise FileExistsError(f'{target} already exists; inspect it instead of overwriting')
    if target == source or source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError('source and installation directories must be separate')
    skills_dir.mkdir(parents=True, exist_ok=True)
    if mode == 'link':
        if os.name == 'nt':
            # Environment variables are data, never interpolate paths into cmd source.
            env = {**os.environ, 'UT_DIFF_LINK': str(target), 'UT_DIFF_SOURCE': str(source)}
            subprocess.run('cmd.exe /d /c mklink /J "%UT_DIFF_LINK%" "%UT_DIFF_SOURCE%"',
                           env=env, check=True, capture_output=True)
        else:
            target.symlink_to(source, target_is_directory=True)
    else:
        stage = Path(tempfile.mkdtemp(prefix='.ut-diff-install-', dir=skills_dir))
        try:
            for p in distribution_files(source):
                out = stage / p.relative_to(source)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, out)
            (stage / '.installation.json').write_text(json.dumps({'source': str(source), 'files': expected}, indent=2), encoding='utf-8')
            stage.rename(target)
        finally:
            if stage.exists() and stage.resolve().is_relative_to(skills_dir) and stage.resolve() != skills_dir:
                shutil.rmtree(stage)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('link', 'copy'), default='link')
    parser.add_argument('--skills-dir', type=Path,
                        default=Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'skills')
    args = parser.parse_args()
    try:
        print(install(Path(__file__).resolve().parents[1], args.skills_dir, args.mode))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(2, str(exc) + '\n')
