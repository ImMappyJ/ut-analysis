"""Deterministic distribution checks; does not publish or prove a complete secret audit."""
import ast
import hashlib
import json
from pathlib import Path
import re

from install_skill import distribution_files

ROOT = Path(__file__).resolve().parents[1]


def main():
    required = ('SKILL.md', 'README.md', 'README_EN.md', 'LICENSE', 'CHANGELOG.md', 'agents/openai.yaml',
                'references/report.schema.json', 'references/quality.schema.json', 'examples/sample_report.html',
                'examples/audit_report.html', 'examples/full_report.html', '.github/workflows/ci.yml')
    for name in required:
        if not (ROOT / name).is_file():
            raise ValueError('missing release file: ' + name)
    provenance = json.loads((ROOT / 'assets/provenance.json').read_text(encoding='utf-8'))
    if hashlib.sha256((ROOT / 'assets/report.css').read_bytes()).hexdigest() != provenance['css_sha256']:
        raise ValueError('baseline stylesheet changed without provenance update')
    for path in distribution_files(ROOT):
        if path.suffix not in ('.py', '.html', '.js', '.css', '.md', '.json', '.yaml', '.go', '.toml'):
            continue
        text = path.read_text(encoding='utf-8')
        # Machine-specific user paths and common credential formats; source review remains required.
        if re.search(r'[A-Za-z]:[\\/](?:Users|Development)[\\/ ]|/(?:Users|home)/[A-Za-z0-9_.-]+/', text):
            raise ValueError('developer-specific absolute path: ' + str(path.relative_to(ROOT)))
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}', text):
            raise ValueError('possible credential: ' + str(path.relative_to(ROOT)))
        if path.suffix == '.py':
            ast.parse(text, filename=str(path))
    if '[TODO' in (ROOT / 'SKILL.md').read_text(encoding='utf-8'):
        raise ValueError('unfinished Skill scaffold')
    print('Distribution structure, Python syntax, CSS provenance and basic privacy checks passed.')


if __name__ == '__main__':
    main()
