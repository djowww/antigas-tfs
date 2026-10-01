"""Recovery sequence shared by the bounded staging maintenance runners."""

import subprocess


RECOVERY_COMMANDS = (
    ("systemctl", "stop", "imperium772-staging"),
    ("systemctl", "set-property", "--runtime", "imperium772-staging", "MemoryMax=1G"),
    ("systemctl", "start", "imperium772"),
)


def recover_staging(run=subprocess.run, check_output=subprocess.check_output):
    """Attempt every recovery action and verify the final unit states."""
    codes = []
    for command in RECOVERY_COMMANDS:
        try:
            codes.append(run(command, timeout=55).returncode)
        except (OSError, subprocess.SubprocessError):
            codes.append(-1)

    states = {}
    for unit in ("imperium772", "imperium772-staging"):
        try:
            states[unit] = check_output(
                ["systemctl", "show", unit, "-p", "ActiveState", "--value"],
                text=True,
                timeout=10,
            ).strip()
        except (OSError, subprocess.SubprocessError):
            states[unit] = "unknown"

    return {
        "recovery_codes": codes,
        "production": states["imperium772"],
        "staging": states["imperium772-staging"],
        "recovery_ok": (
            all(code == 0 for code in codes)
            and states["imperium772"] == "active"
            and states["imperium772-staging"] == "inactive"
        ),
    }


def record_recovery(report, recovery_result, **fields):
    """Persist recovery facts in the report and downgrade false successes."""
    report.update(fields)
    report.update(recovery_result)
    if not recovery_result["recovery_ok"]:
        report["status"] = "failed"
    return recovery_result["recovery_ok"]
