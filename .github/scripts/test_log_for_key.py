"""Regression test for finding r0:F2: the `connected` job must prove that the key never shows in the job log, with only the
Action masking it. Checks (1) check_log_for_key.leaks on logs shaped like the runner's: the two step headers printed before
the Action's mask are allowed, a Scan header that shows the key (mask dropped) and a debug echo are reported; (2) the
workflow does not mask the key itself, and has a follow-up job that needs `connected`, has `actions: read`, downloads the
logs of the api-key legs and runs the checker. Usage: python3 .github/scripts/test_log_for_key.py. Standard library only."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY = "swk_" + "a" * 40
TS = "2026-10-23T10:00:00.0000000Z "
MASKED = [
    TS + "##[group]Run ./", TS + "with:", TS + f"  api-key: {KEY}", TS + "  upload: true", TS + "##[endgroup]",
    TS + "##[group]Run # The key is masked", TS + "env:", TS + f"  SPELLWARDEN_API_KEY: {KEY}", TS + "##[endgroup]",
    TS + "##[group]Run scan", TS + "env:", TS + "  SPELLWARDEN_API_KEY: ***", TS + "##[endgroup]",
    TS + "Connected to Acme as github:github.com/acme/tools (key): ok",
    TS + "##[group]Run python", TS + "env:", TS + "  SW_KEY: ***", TS + "##[endgroup]",
]


def load():
    spec = importlib.util.spec_from_file_location("check_log_for_key", ROOT / ".github/scripts/check_log_for_key.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def job_text(text: str, name: str) -> str:
    start = re.search(rf"^  {name}:\n", text, re.MULTILINE)
    if not start:
        return ""
    rest = text[start.end():]
    end = re.search(r"^  \S", rest, re.MULTILINE)
    return rest[:end.start()] if end else rest


def main() -> int:
    problems: list[str] = []
    checker = load()
    if checker.leaks("\n".join(MASKED), KEY):
        problems.append("a log with only the two allowed headers was reported")
    scan_header = [line.replace("SPELLWARDEN_API_KEY: ***", f"SPELLWARDEN_API_KEY: {KEY}") if "SPELLWARDEN_API_KEY: ***" in line else line for line in MASKED]
    if not checker.leaks("\n".join(scan_header), KEY):
        problems.append("a Scan header that shows the key (the Action's mask dropped) was not reported")
    check_header = [line.replace("SW_KEY: ***", f"SW_KEY: {KEY}") for line in MASKED]
    if not checker.leaks("\n".join(check_header), KEY):
        problems.append("a later step header that shows the key was not reported")
    echoed = MASKED + [TS + f"debug: key={KEY}"]
    if not checker.leaks("\n".join(echoed), KEY):
        problems.append("an echo of the key was not reported")
    text = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    connected = job_text(text, "connected")
    if not connected:
        problems.append("test.yml has no connected job")
    if "::add-mask::" in connected:
        problems.append("the connected job masks the key itself: the Action's own mask is never exercised")
    follow = job_text(text, "connected-log")
    if not follow:
        problems.append("test.yml has no connected-log job that reads the logs of the connected job")
    else:
        for needle, why in (("needs: connected", "needs: connected"), ("actions: read", "permissions: actions: read"),
                            ("for leg in api-key api-key-malformed", "the logs of the api-key and api-key-malformed legs"),
                            ('name="connected ($leg)"', "the lookup of the leg's job by its name"),
                            ("/logs", "the REST log download"), ("check_log_for_key.py", "the checker")):
            if needle not in follow:
                problems.append(f"the connected-log job lacks {why}")
    for problem in problems:
        print("FAIL", problem)
    if not problems:
        print("log-for-key-ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
