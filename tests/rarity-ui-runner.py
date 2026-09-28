"""Run the offline rarity suites in Lua 5.2 (server) and LuaJIT (client).

Usage: python tests/rarity-ui-runner.py --deps ../../tmp/rarity-review/python-deps
Additional positional paths select other Lua suites. No game server is contacted.
"""
import argparse
import importlib
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--deps", type=Path)
parser.add_argument("suites", nargs="*", default=["tests/rarity-ui-tests.lua"])
args = parser.parse_args()
if args.deps:
    sys.path.insert(0, str(args.deps.resolve()))
os.chdir(Path(__file__).resolve().parents[1])
for engine in ("lua52", "luajit21"):
    runtime_class = importlib.import_module("lupa." + engine).LuaRuntime
    for suite in args.suites:
        runtime = runtime_class(unpack_returned_tuples=True)
        runtime.execute(Path(suite).read_text(encoding="utf-8"))
        print(f"PASS {engine}: {suite}", flush=True)
