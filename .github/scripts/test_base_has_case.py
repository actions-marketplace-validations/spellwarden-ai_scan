"""Regression test for the base-settings guard (findings r0:F1, r1:F1): the case needs fixtures/base-settings on the
pull request's base commit, and the guard must find that out without putting the base commit into the checkout (the
scanner's own fetch is what the case exercises). Runs .github/scripts/base_has_case.sh with a stand-in `curl` that
answers a chosen HTTP status and a `git` that fails the test if called. Also asserts the workflow gates every step of
the job after the guard on its output. Usage: python3 .github/scripts/test_base_has_case.py. Standard library only."""
from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE_FILE = "fixtures/base-settings/repo/.spellwarden/config.yml"
FAKE_CURL = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$FAKE_LOG"
if [ "$FAKE_STATUS" = fail ]; then exit 7; fi
printf '%s' "$FAKE_STATUS"
"""
FAKE_GIT = """#!/usr/bin/env bash
echo "git $*" >> "$FAKE_LOG"
exit 99
"""


def guard_output(status: str, tmp: Path) -> tuple[str, str, str]:
    """(what the guard wrote to GITHUB_OUTPUT, its stdout, the calls it made) for a contents API answering `status`
    (`fail`: curl itself fails)."""
    bin_dir, output, log = tmp / f"bin-{status}", tmp / f"output-{status}", tmp / f"log-{status}"
    bin_dir.mkdir()
    for name, text in (("curl", FAKE_CURL), ("git", FAKE_GIT)):
        (bin_dir / name).write_text(text)
        (bin_dir / name).chmod((bin_dir / name).stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "FAKE_STATUS": status,
           "FAKE_LOG": str(log), "BASE_SHA": "a" * 40, "GH_TOKEN": "t", "GITHUB_API_URL": "https://api.github.com",
           "GITHUB_REPOSITORY": "spellwarden-ai/scan", "GITHUB_OUTPUT": str(output)}
    result = subprocess.run(["bash", str(ROOT / ".github/scripts/base_has_case.sh"), CASE_FILE], capture_output=True,
                            text=True, env=env)
    calls = log.read_text() if log.exists() else ""
    if result.returncode != 0:
        return f"guard exited {result.returncode}: {result.stderr.strip()}", result.stdout, calls
    return output.read_text().strip(), result.stdout, calls


def job_text() -> str:
    text = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    start = text.index("\n  base-settings:\n")
    end = text.find("\n  telemetry:\n", start)
    return text[start:end]


def main() -> int:
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for status, expected, notice in (("404", "present=false", True), ("200", "present=true", False),
                                         ("500", "present=true", False), ("fail", "present=true", False)):
            out, stdout, calls = guard_output(status, tmp)
            if out != expected:
                problems.append(f"contents API {status}: guard wrote {out!r}, expected {expected!r}")
            if notice != stdout.startswith("::notice::"):
                problems.append(f"contents API {status}: notice {'missing' if notice else 'unexpected'} ({stdout!r})")
            if "git " in calls:
                problems.append(f"contents API {status}: the guard ran git, which may put the base commit in the clone")
            if f"/repos/spellwarden-ai/scan/contents/{CASE_FILE}?ref={'a' * 40}" not in calls:
                problems.append(f"contents API {status}: the guard did not ask for the case file at the base commit")
    job = job_text()
    steps = re.split(r"^      - ", job, flags=re.M)[1:]
    guard_at = next((i for i, step in enumerate(steps) if "base_has_case.sh" in step), None)
    guard_id = re.search(r"^\s+id:\s*(\w+)\s*$", steps[guard_at], re.M) if guard_at is not None else None
    if guard_at is None or not guard_id:
        problems.append("the base-settings job has no step with an id that runs base_has_case.sh")
    else:
        gate = f"steps.{guard_id.group(1)}.outputs.present == 'true'"
        for step in steps[guard_at + 1:]:
            if gate not in step:
                problems.append(f"a step after the guard is not gated on {gate}: {step.splitlines()[0]}")
    for problem in problems:
        print(f"FAIL {problem}")
    if not problems:
        print("base-has-case-ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
