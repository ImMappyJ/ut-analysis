"""Remove only clean, ownership-verified worktrees in a context manifest."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ut_diff_report import configure_cli
from ut_diff_report.core import load_data
from ut_diff_report.git_context import cleanup

configure_cli()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    args = parser.parse_args()
    failures = []
    for context in load_data(args.manifest)['projects']:
        try:
            print(context['project_id'] + ': ' + cleanup(context))
        except (OSError, ValueError) as exc:
            failures.append(str(exc))
    if failures:
        parser.exit(2, '\n'.join(failures) + '\n')
