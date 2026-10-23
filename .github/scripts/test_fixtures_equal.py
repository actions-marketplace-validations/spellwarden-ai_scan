"""The shared files are copies (O3 plan P13): `fixtures/` must equal the command repository's `fixtures/repos` and
`.github/scripts/fake_api.py` must equal its `fixtures/ci/fake_api.py`, byte for byte. The comparison is the one of
`scripts/release-wrappers.py` there (`_tree`): relative POSIX path to bytes, ignoring `__pycache__` and `.pyc`. The
sibling checkout is `../spellwarden-oss`; without it the test prints a skip line and passes, as the equality test
in that repository does for a missing wrapper. Usage: python3 .github/scripts/test_fixtures_equal.py.
Standard library only."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIBLING = ROOT.parent / "spellwarden-oss"


def _cache(relative: Path) -> bool:
    """Python's byte-code cache, which the fixture scripts leave behind and no repository tracks."""
    return "__pycache__" in relative.parts or relative.suffix == ".pyc"


def tree(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*"))
            if path.is_file() and not _cache(path.relative_to(root))}


def differences(own: dict[str, bytes], other: dict[str, bytes], label: str) -> list[str]:
    problems = [f"{label}: {name} is only in the Action" for name in sorted(set(own) - set(other))]
    problems += [f"{label}: {name} is only in spellwarden-oss" for name in sorted(set(other) - set(own))]
    problems += [f"{label}: {name} differs" for name in sorted(set(own) & set(other)) if own[name] != other[name]]
    return problems


def main() -> int:
    if not SIBLING.is_dir():
        print(f"skip: {SIBLING} is not checked out")
        return 0
    problems = differences(tree(ROOT / "fixtures"), tree(SIBLING / "fixtures" / "repos"), "fixtures")
    if not (SIBLING / "fixtures" / "repos").is_dir():
        problems.append("fixtures: spellwarden-oss has no fixtures/repos")
    fake, original = ROOT / ".github" / "scripts" / "fake_api.py", SIBLING / "fixtures" / "ci" / "fake_api.py"
    if not fake.is_file() or not original.is_file():
        problems.append("fake_api.py: missing in the Action or in spellwarden-oss")
    elif fake.read_bytes() != original.read_bytes():
        problems.append("fake_api.py differs from spellwarden-oss/fixtures/ci/fake_api.py")
    script, original_script = ROOT / ".github" / "scripts" / "connected-script.json", SIBLING / "fixtures" / "ci" / "script.json"
    if not script.is_file() or not original_script.is_file():
        problems.append("connected-script.json: missing in the Action or in spellwarden-oss")
    elif script.read_bytes() != original_script.read_bytes():
        problems.append("connected-script.json differs from spellwarden-oss/fixtures/ci/script.json")
    for problem in problems:
        print(f"FAIL {problem}")
    if not problems:
        print("fixtures-equal-ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
