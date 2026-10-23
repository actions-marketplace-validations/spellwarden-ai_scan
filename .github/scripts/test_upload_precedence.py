"""Regression test for finding r0:F1: the `upload` input must not override `connected.upload` of the settings file.
The scanner ranks SPELLWARDEN_UPLOAD above the file (settings.py: flag, environment, file, default true), so the Scan
step must export it only when the input turns the upload off. The test (1) checks that the Scan step's `env:` block does
not set SPELLWARDEN_UPLOAD from the input, and (2) runs the one `if ... fi` line of the Scan step's script that exports
it, with the four combinations of the input and a job-level SPELLWARDEN_UPLOAD, and reads what the scanner would see.
Usage: python3 .github/scripts/test_upload_precedence.py. Standard library only."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPORT = re.compile(r'^\s*(if \[ "\$SW_CONNECTED_UPLOAD" = "false" \]; then export SPELLWARDEN_UPLOAD=false; fi)\s*$',
                    re.MULTILINE)


def scan_step() -> str:
    text = (ROOT / "action.yml").read_text(encoding="utf-8")
    start = text.index("\n    - name: Scan\n")
    end = text.index("\n    - name:", start + 1)
    return text[start:end]


def seen_by_scanner(line: str, upload_input: str, job_value: str | None) -> str | None:
    """The SPELLWARDEN_UPLOAD the scanner process would get; None when unset."""
    env = {key: value for key, value in os.environ.items() if key != "SPELLWARDEN_UPLOAD"}
    env["SW_CONNECTED_UPLOAD"] = upload_input
    if job_value is not None:
        env["SPELLWARDEN_UPLOAD"] = job_value
    result = subprocess.run(["bash", "-c", line + '\nif [ -n "${SPELLWARDEN_UPLOAD+x}" ]; then printf "%s" "$SPELLWARDEN_UPLOAD"; else printf "UNSET"; fi'],
                            capture_output=True, text=True, env=env)
    return None if result.stdout == "UNSET" else result.stdout


def main() -> int:
    problems: list[str] = []
    step = scan_step()
    env_block = step[step.index("      env:\n"):step.index("      run: |")]
    if re.search(r"^\s*SPELLWARDEN_UPLOAD:", env_block, re.MULTILINE):
        problems.append("the Scan step's env block sets SPELLWARDEN_UPLOAD: the input would beat the settings file")
    if not re.search(r"^\s*SW_CONNECTED_UPLOAD:\s*\$\{\{ inputs\.upload \}\}\s*$", env_block, re.MULTILINE):
        problems.append("the Scan step does not pass the upload input as SW_CONNECTED_UPLOAD")
    found = EXPORT.search(step)
    if not found:
        problems.append("the Scan step has no line that exports SPELLWARDEN_UPLOAD=false only when the input is false")
    else:
        line = found.group(1)
        for upload_input, job_value, expected in (("true", None, None), ("true", "false", "false"),
                                                  ("false", None, "false"), ("false", "true", "false")):
            got = seen_by_scanner(line, upload_input, job_value)
            if got != expected:
                problems.append(f"upload={upload_input} with a job SPELLWARDEN_UPLOAD={job_value!r}: the scanner sees {got!r}, "
                                f"expected {expected!r}")
    for problem in problems:
        print(f"FAIL {problem}")
    if not problems:
        print("upload-precedence-ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
