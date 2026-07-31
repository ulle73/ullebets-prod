from __future__ import annotations

import re


def _strip_trailing_backslash(line: str) -> str:
    stripped = line.rstrip()
    if stripped.endswith("\\"):
        stripped = stripped[:-1].rstrip()
    return stripped


def render_workflow_command(command: str, *, dry_run: bool) -> str:
    text = str(command or "")
    if dry_run:
        return text

    output_lines: list[str] = []
    for original_line in text.splitlines():
        line = re.sub(r"(?<!\S)--dry-run(?=(?:\s|$|[)\\]))", "", original_line)
        if line.strip() == "":
            if "--dry-run" in original_line and output_lines:
                output_lines[-1] = _strip_trailing_backslash(output_lines[-1])
            continue
        output_lines.append(line.rstrip())

    rendered = "\n".join(output_lines).rstrip()
    return f"{rendered}\n" if rendered else ""
