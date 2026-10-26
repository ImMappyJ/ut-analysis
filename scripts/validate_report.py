"""Check standalone HTML structure, embedded evidence and count invariants."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
configure_cli()
from ut_diff_report.core import ValidationError, validate_html


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    try:
        validate_html(args.report)
        print('Report structure and accounting valid; browser interaction requires separate verification.')
    except (OSError, ValidationError) as exc:
        parser.exit(2, str(exc) + '\n')
