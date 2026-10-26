"""Render Agent-authored canonical data into the fixed offline report template."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
configure_cli()
from ut_diff_report.core import ValidationError, load_data, render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', help='canonical JSON prepared by the Agent')
    parser.add_argument('--workspace', type=Path, default=Path.cwd(), help='caller workspace; defaults to current directory')
    parser.add_argument('--output', type=Path, help='relative to workspace; default docs/ut_result.html')
    parser.add_argument('--replace', action='store_true', help='only for explicitly authorized regeneration')
    args = parser.parse_args()
    try:
        print(render(load_data(args.data), workspace=args.workspace, output=args.output, replace=args.replace))
    except (OSError, ValidationError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
