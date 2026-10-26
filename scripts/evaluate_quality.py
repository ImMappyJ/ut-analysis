"""Validate structured audit/full evidence and reproduce quality gates without semantic guessing."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
from ut_diff_report.core import load_data, validate
from ut_diff_report.quality import evaluate_quality

configure_cli()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        data = load_data(args.data)
        validate(data)
        text = json.dumps(evaluate_quality(data), ensure_ascii=False, indent=2) + '\n'
        if args.output:
            if args.output.exists():
                raise FileExistsError('choose a fresh evaluation path')
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding='utf-8')
        else:
            print(text, end='')
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')
