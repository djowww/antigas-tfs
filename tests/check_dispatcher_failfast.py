"""Check the isolated real-core dispatcher fixture's expected fail-fast exit."""

import argparse
from pathlib import Path
import subprocess
import sys


TIMEOUT_SECONDS = 5
EXPECTED_EXIT = 86
QUEUED_MARKER = "DISPATCHER_FAILFAST_TASKS_QUEUED"
EXPECTED_MARKER = "DISPATCHER_FAILFAST_EXPECTED_TERMINATION"
POSTERIOR_MARKER = "DISPATCHER_FAILFAST_POSTERIOR_EXECUTED"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path, help="Built dispatcher-failfast-tests executable")
    args = parser.parse_args()
    executable = args.executable.resolve()
    if not executable.is_file():
        print("FAIL: dispatcher fixture executable is missing.", file=sys.stderr)
        return 1

    try:
        result = subprocess.run(
            [str(executable)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("FAIL: dispatcher fixture exceeded its timeout.", file=sys.stderr)
        return 1
    except OSError:
        print("FAIL: dispatcher fixture could not be started.", file=sys.stderr)
        return 1

    if POSTERIOR_MARKER in result.stdout or POSTERIOR_MARKER in result.stderr:
        print("FAIL: dispatcher executed the task after the exception.", file=sys.stderr)
        return 1
    if result.returncode != EXPECTED_EXIT:
        print("FAIL: dispatcher fixture did not produce the expected exit status.", file=sys.stderr)
        return 1
    if result.stdout.splitlines() != [QUEUED_MARKER, EXPECTED_MARKER] or result.stderr:
        print("FAIL: dispatcher fixture produced missing or unexpected diagnostics.", file=sys.stderr)
        return 1

    print("PASS: real dispatcher failed fast before executing its queued posterior task.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
