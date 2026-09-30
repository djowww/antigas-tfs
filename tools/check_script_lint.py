"""Analyze repository shell scripts and workflows without executing their bodies."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from script_lint_tools import TOOLS


ROOT = Path(__file__).resolve().parents[1]


def run(command):
    environment = dict(os.environ)
    # Local ShellCheck options/config must not silently change the CI scope.
    environment["SHELLCHECK_OPTS"] = "--norc"
    return subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                          capture_output=True, timeout=120, check=False, env=environment)


def files(*patterns):
    result = run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *patterns])
    if result.returncode:
        raise RuntimeError(result.stderr)
    return sorted(set(filter(None, result.stdout.split("\0"))))


def executable(name, directory):
    if directory:
        candidate = directory / (name + (".exe" if os.name == "nt" else ""))
        if not candidate.is_file():
            raise RuntimeError(f"Missing pinned tool: {candidate}")
        return str(candidate.resolve())
    candidate = shutil.which(name)
    if not candidate:
        raise RuntimeError(f"Missing {name}; use tools/script_lint_tools.py or --tool-directory.")
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-directory", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "build/script-lint-results")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    tools = {name: executable(name, args.tool_directory) for name in TOOLS}
    versions = {}
    for name, path in tools.items():
        result = run([path, "-version" if name == "actionlint" else "--version"])
        text = result.stdout + result.stderr
        if result.returncode or not re.search(r"(?m)^(?:version: )?" + re.escape(TOOLS[name]["version"]) + r"$", text):
            raise RuntimeError(f"Expected {name} {TOOLS[name]['version']}; got {text.strip()}")
        versions[name] = {"version": TOOLS[name]["version"], "output": text.strip(),
                          "executable_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    shell = files("*.sh", "*.bash")
    workflows = files(".github/workflows/*.yml", ".github/workflows/*.yaml")
    if not shell or not workflows:
        raise RuntimeError("Incomplete analysis: expected shell scripts and workflows.")
    report = {"tools": versions, "scope": {"shell": shell, "workflows": workflows},
              "source_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in shell + workflows},
              "baseline": "none", "repository_suppressions": "no extra CLI exclusions",
              "workflow_shellcheck_policy": "actionlint upstream defaults", "checks": {}}
    receipt = args.tool_directory / "receipts.json" if args.tool_directory else None
    if receipt and receipt.is_file():
        report["archive_receipts"] = json.loads(receipt.read_text(encoding="utf-8"))
    commands = {
        "shellcheck": [tools["shellcheck"], "--norc", "--format=json1", "--severity=style", *shell],
        # Disable only the unrelated optional Python linter. ShellCheck remains explicit.
        "actionlint": [tools["actionlint"], "-no-color", "-shellcheck", tools["shellcheck"], "-pyflakes", "", *workflows],
    }
    failed = False
    for name, command in commands.items():
        result = run(command)
        (args.output / f"{name}.stdout.txt").write_text(result.stdout, encoding="utf-8")
        (args.output / f"{name}.stderr.txt").write_text(result.stderr, encoding="utf-8")
        report["checks"][name] = {"exit_code": result.returncode}
        if name == "shellcheck":
            parsed = json.loads(result.stdout)
            (args.output / "shellcheck.json").write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")
            report["checks"][name]["diagnostics"] = len(parsed["comments"])
            failed |= bool(parsed["comments"])
        failed |= result.returncode != 0
        print(f"{name}: exit {result.returncode}, {len(shell) if name == 'shellcheck' else len(workflows)} files")
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
    report["status"] = "failed" if failed else "passed"
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
