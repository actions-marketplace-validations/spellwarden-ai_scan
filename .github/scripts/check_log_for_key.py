"""Fails when a job log shows a CI key (finding r0:F2; spec 10, invariant 2: the Action never prints the key). The key the
`connected` job passes is a plain test value that nothing masks but the Action itself (`::add-mask::` in its Validate step),
so a log that shows it means the Action did not mask it or printed it. The runner prints the evaluated inputs of a step
before the step runs, hence before any mask of the Action can apply: the `api-key:` line of the `with:` block of the Action's
own step and the first `SPELLWARDEN_API_KEY:` line (the env of the Validate step, which registers the mask) are the only
places the key may appear; every other line that shows it is reported. The key comes from the environment (SW_KEY), not from
the command line. Usage: SW_KEY=... python3 -I .github/scripts/check_log_for_key.py LOGFILE...
Exits 1 listing every leak. Standard library only."""
from __future__ import annotations

import os
import re
import sys

HEADER_BEFORE_MASK = (re.compile(r"^(\S+\s+)?\s*api-key: (?P<value>.*)$"), re.compile(r"^(\S+\s+)?\s*SPELLWARDEN_API_KEY: (?P<value>.*)$"))


def leaks(log: str, key: str) -> list[str]:
    """The lines of `log` that show `key`, other than the one allowed `api-key:` line and the one allowed
    `SPELLWARDEN_API_KEY:` line (the step headers the runner prints before the Action's mask is registered)."""
    allowed = [1, 1]
    found: list[str] = []
    for number, line in enumerate(log.splitlines(), start=1):
        if key not in line:
            continue
        for index, pattern in enumerate(HEADER_BEFORE_MASK):
            match = pattern.match(line)
            if match and match.group("value").strip() == key and allowed[index] > 0:
                allowed[index] -= 1
                break
        else:
            found.append(f"line {number}")
    return found


def main(argv: list[str]) -> int:
    key = os.environ.get("SW_KEY", "")
    if not key or len(argv) < 2:
        print("usage: SW_KEY=<key> check_log_for_key.py LOGFILE...", file=sys.stderr)
        return 2
    failed = False
    for path in argv[1:]:
        with open(path, encoding="utf-8", errors="replace") as handle:
            found = leaks(handle.read(), key)
        if found:
            failed = True
            print(f"FAIL {os.path.basename(path)}: the key is shown at {', '.join(found)}")
        else:
            print(f"ok {os.path.basename(path)}: the key is not shown after the Action's mask")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
