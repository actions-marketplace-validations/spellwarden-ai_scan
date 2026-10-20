"""Static checks of the shell contract (spec 9.2): no `${{` inside any `run:` text (block or inline), every
remote `uses:` pinned by a 40-hex commit, the scanner's text report (hostile paths, spec 6.13) printed only
between `::stop-commands::<token>` and the matching `::<token>::`, and every Python the Action runs started in
isolated mode (`-I`): the working directory is the scanned checkout, whose `json.py` or `spellwarden_cli/` would
otherwise be imported first (spec 9.2). Usage: python3 .github/scripts/lint_action.py FILE...
Exits 1 listing every problem. Standard library only."""
from __future__ import annotations

import re
import sys

USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)")
RUN = re.compile(r"^(\s*(?:-\s+)?)run:\s*(.*)$")
PINNED = re.compile(r"[^@\s]+@[0-9a-f]{40}")


SCANNER = re.compile(r'-m\s+spellwarden_cli\s+"\$\{args\[@\]\}"')
STOP = re.compile(r'echo\s+"::stop-commands::\$\w+"')
RESUME = re.compile(r'echo\s+"::\$\w+::"')
PYTHON = re.compile(r'(?:"\$(?:SW_PY|SW_BASE_PY|venv_py|candidate)"|\bpy -3)\s+(-\S*)')


def log_problems(path: str, block: list[tuple[int, str]]) -> list[str]:
    """The text report goes to the job log, where a line that starts with `::` is a workflow command and a
    pull request author names the directories (spec 6.13): a step that prints it must stop the commands first
    and resume them after the scanner has exited."""
    text = "\n".join(line for _, line in block)
    if "--format text" not in text:
        return []
    runs = [number for number, line in block if SCANNER.search(line)]
    stops = [number for number, line in block if STOP.search(line)]
    resumes = [number for number, line in block if RESUME.search(line)]
    if not runs:
        return []
    if not (stops and stops[0] < runs[0] and any(number > runs[-1] for number in resumes)):
        return [f"{path}:{runs[0]}: the scanner's text report is printed outside ::stop-commands::<token> ... ::<token>::"]
    return []


def problems_of(path: str) -> list[str]:
    problems: list[str] = []
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    block_column: int | None = None
    block: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        if block_column is not None:
            indent = len(line) - len(line.lstrip(" "))
            if not line.strip() or indent > block_column:
                block.append((number, line))
                if "${{" in line:
                    problems.append(f"{path}:{number}: expression inside run: text")
                for call in PYTHON.finditer(line):
                    if call.group(1) != "-I":
                        problems.append(f"{path}:{number}: Python started without -I reads modules from the checkout")
                continue
            problems += log_problems(path, block)
            block_column = None
            block = []
        run = RUN.match(line)
        if run:
            value = run.group(2).strip()
            if value[:1] in ("|", ">"):
                block_column = len(run.group(1))
                block = []
            elif "${{" in value:
                problems.append(f"{path}:{number}: expression inside run: text")
        uses = USES.match(line)
        if uses:
            reference = uses.group(1)
            if not reference.startswith("./") and not PINNED.fullmatch(reference):
                problems.append(f"{path}:{number}: {reference} is not pinned by a full commit SHA")
    if block_column is not None:
        problems += log_problems(path, block)
    return problems


def main(argv: list[str]) -> int:
    found = [problem for path in argv[1:] for problem in problems_of(path)]
    for problem in found:
        print(problem)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
