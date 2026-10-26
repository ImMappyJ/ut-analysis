"""Validate schema, unique entry accounting and runtime evidence; print computed statistics."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
configure_cli()
from ut_diff_report.core import ValidationError, load_data, validate


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data')
    args = parser.parse_args()
    try:
        print(json.dumps(validate(load_data(args.data)), ensure_ascii=False, indent=2))
    except (OSError, ValidationError) as exc:
        parser.exit(2, str(exc) + '\n')
