"""Resolve a project within a caller workspace and collect import-free AST evidence."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
configure_cli()
from ut_diff_report.discovery import ResolutionError, resolve_project, scan_python


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', help='explicit path or unambiguous workspace project name')
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--id', choices=('A', 'B'), required=True)
    parser.add_argument('--language', choices=('python', 'go'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        root = resolve_project(args.project, args.workspace)
        output = args.output if args.output.is_absolute() else args.workspace.resolve() / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError('use a fresh inventory path')
        if args.language == 'go':
            if not shutil.which('go'):
                parser.exit(2, 'Go is unavailable; use a native collector or record NOT RUN.\n')
            subprocess.run(['go', 'run', str(Path(__file__).with_name('scan_go.go')), str(root), args.id, str(output)],
                           check=True)
        else:
            output.write_text(json.dumps(scan_python(root, args.id), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(output)
    except (OSError, ResolutionError, subprocess.CalledProcessError) as exc:
        parser.exit(2, str(exc) + '\n')
