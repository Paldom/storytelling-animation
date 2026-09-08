#!/usr/bin/env python3
"""Run every bundled skill script's `--self-test` (the one runnable check per script).

Skill scripts ship to users' machines, so each carries its own self-test; this
runner makes `make check` execute all of them without a test framework.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    scripts = sorted((ROOT / "skills").glob("*/scripts/*.py"))
    failed = 0
    for script in scripts:
        if "--self-test" not in script.read_text(encoding="utf-8"):
            print(f"SKIP  {script.relative_to(ROOT)} (no --self-test)")
            continue
        proc = subprocess.run(
            [sys.executable, str(script), "--self-test"],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        status = "OK  " if proc.returncode == 0 else "FAIL"
        print(f"{status}  {script.relative_to(ROOT)}")
        if proc.returncode != 0:
            failed += 1
            print(proc.stdout + proc.stderr)
    print(
        f"{'FAIL' if failed else 'OK'}: {failed} failing self-test(s) of {len(scripts)} script(s)"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
