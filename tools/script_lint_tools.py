"""Fetch the pinned official linters; never run a deployment script."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import tarfile
import urllib.request
import zipfile


TOOLS = {
    "actionlint": {
        "version": "1.7.12",
        "base": "https://github.com/rhysd/actionlint/releases/download/v1.7.12/",
        "Linux": ("actionlint_1.7.12_linux_amd64.tar.gz", "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8", "actionlint"),
        "Windows": ("actionlint_1.7.12_windows_amd64.zip", "6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9", "actionlint.exe"),
    },
    "shellcheck": {
        "version": "0.11.0",
        "base": "https://github.com/koalaman/shellcheck/releases/download/v0.11.0/",
        "Linux": ("shellcheck-v0.11.0.linux.x86_64.tar.xz", "8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198", "shellcheck-v0.11.0/shellcheck"),
        "Windows": ("shellcheck-v0.11.0.zip", "8a4e35ab0b331c85d73567b12f2a444df187f483e5079ceffa6bda1faa2e740e", "shellcheck.exe"),
    },
}


def install(directory):
    system = platform.system()
    if system not in ("Linux", "Windows") or platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("Pinned linter archives support Linux/Windows x86-64 only.")
    directory.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for name, spec in TOOLS.items():
        filename, expected, member = spec[system]
        archive = directory / filename
        if not archive.exists():
            request = urllib.request.Request(spec["base"] + filename, headers={"User-Agent": "Antigas-script-lint"})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read(20 * 1024 * 1024 + 1)
            if len(data) > 20 * 1024 * 1024:
                raise RuntimeError(f"Oversized linter archive: {filename}")
        else:
            data = archive.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise RuntimeError(f"SHA-256 mismatch for {filename}: {actual}")
        if not archive.exists():
            archive.write_bytes(data)
        # Extract only the expected executable, never arbitrary archive paths.
        if filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as source:
                binary = source.read(member)
        else:
            with tarfile.open(fileobj=io.BytesIO(data)) as source:
                entry = source.getmember(member)
                if not entry.isfile():
                    raise RuntimeError(f"Expected regular executable: {member}")
                with source.extractfile(entry) as stream:
                    binary = stream.read()
        target = directory / Path(member).name
        target.write_bytes(binary)
        if system != "Windows":
            target.chmod(0o755)
        receipts[name] = {"version": spec["version"], "url": spec["base"] + filename,
                          "archive_sha256": actual, "executable_sha256": hashlib.sha256(binary).hexdigest()}
        print(f"Verified {name} {spec['version']}: {actual}")
    (directory / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    install(parser.parse_args().directory.resolve())
