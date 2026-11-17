"""Write generated tables into a markdown doc between AUTO markers (keeps hand-written prose)."""
from __future__ import annotations

from pathlib import Path


def write_auto_block(doc: Path, tag: str, block: str) -> None:
    """Replace the text between `<!-- BEGIN AUTO: tag -->` and `<!-- END AUTO: tag -->`.

    If the doc or the markers do not exist yet, the block is appended with its markers.
    """
    begin, end = f"<!-- BEGIN AUTO: {tag} -->", f"<!-- END AUTO: {tag} -->"
    doc = Path(doc)
    text = doc.read_text(encoding="utf-8") if doc.exists() else ""
    new = f"{begin}\n{block.rstrip()}\n{end}"
    if begin in text and end in text:
        head, rest = text.split(begin, 1)
        _, tail = rest.split(end, 1)
        text = head + new + tail
    else:
        text = (text.rstrip() + "\n\n" if text else "") + new + "\n"
    doc.write_text(text, encoding="utf-8")
