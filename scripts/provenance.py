"""Equation explanations and reader-visible sources for equations, tables, and figures."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final, assert_never

from errors import ManuscriptError
from manuscript import (
    Block,
    EquationBlock,
    FigureBlock,
    HeadingBlock,
    Manuscript,
    ParagraphBlock,
    TableBlock,
    paragraph_text,
)

OWN_WORK: Final = ("이 문서", "이 교재", "본 연구", "this document")
EQ_NUMBER_RE: Final = re.compile(r"\((\d+)\)")
_NAME: Final = r"[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’\-]+"
_NAMES: Final = rf"{_NAME}(?:\s+{_NAME}){{0,5}}(?:\s+et\s+al\.)?"
AUTHOR_YEAR_RE: Final = re.compile(rf"(?:\(\s*)?{_NAMES}\s*(?:,\s*|\(\s*)\d{{4}}\s*\)?")
PATH_RE: Final = re.compile(
    r"(?<![\w./\\])(?:"
    r"[A-Za-z]:[\\/](?:[^\s\"'`<>|]+[\\/])*[^\s\"'`<>|]+\.[A-Za-z0-9]{1,8}"
    r"|/(?:[\w.\-]+/)*[\w.\-]+\.[A-Za-z0-9]{1,8}"
    r"|\.{1,2}/[\w.\-]+\.[A-Za-z0-9]{1,8}"
    r"|(?:[\w.\-]+/)+[\w.\-]+\.[A-Za-z0-9]{1,8}"
    r")"
)
_MIN_CITE: Final = 6


def check_provenance(manuscript: Manuscript, base: Path) -> None:
    """Require explanations and a resolvable source on equations, tables, and figures."""
    _check_equation_runs(manuscript)
    _check_table_sources(manuscript)
    cites = _known_cites(manuscript)
    for block in manuscript.blocks:
        match block:
            case EquationBlock(source=source) | TableBlock(source=source) | FigureBlock(source=source):
                _validate_source(source, cites, base)
            case HeadingBlock() | ParagraphBlock():
                pass
            case unreachable:
                assert_never(unreachable)


def _check_equation_runs(manuscript: Manuscript) -> None:
    blocks = manuscript.blocks
    index = 0
    total = len(blocks)
    while index < total:
        if not _is_equation(blocks[index]):
            index += 1
            continue
        start = index
        while index < total and _is_equation(blocks[index]):
            index += 1
        _require_explanation(blocks, start, index)


def _require_explanation(blocks: list[Block], start: int, end: int) -> None:
    if end >= len(blocks):
        raise ManuscriptError("missing_equation_explanation", "body")
    explanation = _body_text(blocks[end])
    if explanation is None:
        raise ManuscriptError("missing_equation_explanation", "body")
    window = _paragraphs_until_heading(blocks, end)
    for block in blocks[start:end]:
        match block:
            case EquationBlock(source=source, lines=lines):
                if source not in explanation:
                    raise ManuscriptError("missing_equation_source", "source")
                _require_numbers(lines, window)
            case unreachable:
                assert_never(unreachable)


def _body_text(block: Block) -> str | None:
    match block:
        case ParagraphBlock(role="body", text=text):
            return text
        case ParagraphBlock() | HeadingBlock() | EquationBlock() | TableBlock() | FigureBlock():
            return None
        case unreachable:
            assert_never(unreachable)


def _require_numbers(lines: list[str], window: list[str]) -> None:
    for line in lines:
        for number in EQ_NUMBER_RE.findall(line):
            token = f"({number})"
            if not any(token in paragraph for paragraph in window):
                raise ManuscriptError("missing_equation_explanation", f"eq:{number}")


def _paragraphs_until_heading(blocks: list[Block], start: int) -> list[str]:
    found: list[str] = []
    for block in blocks[start:]:
        match block:
            case HeadingBlock():
                return found
            case ParagraphBlock(text=text):
                found.append(text)
            case EquationBlock() | TableBlock() | FigureBlock():
                pass
            case unreachable:
                assert_never(unreachable)
    return found


def _check_table_sources(manuscript: Manuscript) -> None:
    blocks = manuscript.blocks
    for index, block in enumerate(blocks):
        match block:
            case TableBlock(source=source):
                if not _adjacent_has_source(blocks, index, source):
                    raise ManuscriptError("missing_table_source", "source")
            case HeadingBlock() | ParagraphBlock() | EquationBlock() | FigureBlock():
                pass
            case unreachable:
                assert_never(unreachable)


def _adjacent_has_source(blocks: list[Block], index: int, source: str) -> bool:
    neighbors: list[Block] = []
    if index > 0:
        neighbors.append(blocks[index - 1])
    if index + 1 < len(blocks):
        neighbors.append(blocks[index + 1])
    return any(_contains(paragraph_text(block), source) for block in neighbors)


def _contains(text: str | None, needle: str) -> bool:
    return text is not None and needle in text


def _validate_source(source: str, cites: list[str], base: Path) -> None:
    for span in AUTHOR_YEAR_RE.finditer(source):
        if not _span_covered(source, span.start(), span.end(), cites):
            raise ManuscriptError("missing_reference", span.group(0))
    paths = _local_paths(source)
    for token in paths:
        if not _file_exists(token, base):
            raise ManuscriptError("missing_source_file", token)
    if not any(cite in source for cite in cites) and not paths and not _has_own_work(source):
        raise ManuscriptError("unsourced", "source")


def _known_cites(manuscript: Manuscript) -> list[str]:
    found: list[str] = []
    for ref in manuscript.references:
        cite = ref.cite
        if cite is not None and len(cite) >= _MIN_CITE and any(char.isalpha() for char in cite):
            found.append(cite)
    return found


def _span_covered(text: str, start: int, end: int, cites: list[str]) -> bool:
    for cite in cites:
        pos = text.find(cite)
        while pos != -1:
            if start < pos + len(cite) and pos < end:
                return True
            pos = text.find(cite, pos + 1)
    return False


def _local_paths(text: str) -> list[str]:
    found: list[str] = []
    for match in PATH_RE.finditer(text):
        if _inside_url(text, match.start()):
            continue
        found.append(match.group(0))
    return found


def _inside_url(text: str, start: int) -> bool:
    prefix = text[max(0, start - 8) : start + 1].lower()
    return "://" in prefix or prefix.endswith(("http:", "https:"))


def _file_exists(token: str, base: Path) -> bool:
    raw = Path(token)
    path = raw if raw.is_absolute() else base / raw
    return path.is_file()


def _has_own_work(text: str) -> bool:
    return any(phrase in text for phrase in OWN_WORK)


def _is_equation(block: Block) -> bool:
    match block:
        case EquationBlock():
            return True
        case HeadingBlock() | ParagraphBlock() | TableBlock() | FigureBlock():
            return False
        case unreachable:
            assert_never(unreachable)
