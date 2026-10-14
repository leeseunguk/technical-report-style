"""Optional source ledger. Parsed at the boundary and never rendered."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Final, assert_never

from pydantic import Field, TypeAdapter, ValidationError

from errors import ManuscriptError
from manuscript import (
    EquationBlock,
    FigureBlock,
    FrozenModel,
    HeadingBlock,
    LoadedManuscript,
    Manuscript,
    ParagraphBlock,
    TableBlock,
    schema_detail,
)
from provenance import EQ_NUMBER_RE, _MIN_CITE, _file_exists

UNVERIFIED: Final = ("확인하지 못", "not verified")
ITEM_PATTERN: Final = (
    r"^(?:eq:\d+|fig:[A-Za-z0-9][A-Za-z0-9._:-]{0,64}|table:\d+|claim:\S+)$"
)


class PdfAnchor(FrozenModel):
    """A literature locator. The page is not opened."""

    pdf: str = Field(min_length=1)
    page: int = Field(ge=1)
    locator: str = Field(min_length=1)


class FileAnchor(FrozenModel):
    """A local file and the symbol that was checked."""

    file: str = Field(min_length=1)
    symbol: str = Field(min_length=1)


class LedgerKind(StrEnum):
    """How the item relates to the cited source."""

    LITERATURE = "literature"
    ADAPTED = "adapted"
    DERIVED = "derived"
    MEASURED = "measured"
    CONVENTION = "convention"
    CONCEPT = "concept"


class LedgerStatus(StrEnum):
    """Whether the author checked the locator, not whether the locator is true."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class LedgerEntry(FrozenModel):
    """One ledger row. Extra keys are rejected at the boundary."""

    item: str = Field(min_length=1, pattern=ITEM_PATTERN)
    location: str = Field(min_length=1)
    citation: str = Field(min_length=1)
    kind: LedgerKind
    checked_against: PdfAnchor | FileAnchor
    status: LedgerStatus


_LEDGER: Final = TypeAdapter(list[LedgerEntry])


class ItemKind(StrEnum):
    """Ledger item prefix."""

    EQ = "eq"
    FIG = "fig"
    TABLE = "table"
    CLAIM = "claim"


def load_ledger(path: Path) -> list[LedgerEntry]:
    """Parse a ledger JSON list. This is the only ledger boundary."""
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ManuscriptError("malformed_manuscript", "ledger not utf-8") from None
    except OSError:
        raise ManuscriptError("malformed_manuscript", path.name) from None
    try:
        return _LEDGER.validate_json(raw)
    except ValidationError as exc:
        raise ManuscriptError("malformed_manuscript", schema_detail(exc)) from None


def check_ledger(loaded: LoadedManuscript, ledger_path: Path) -> None:
    """Check ledger coverage and anchors. Nothing here is written into the DOCX."""
    entries = load_ledger(ledger_path)
    missing = sorted(_required_items(loaded.manuscript) - {entry.item for entry in entries})
    if missing:
        raise ManuscriptError("missing_ledger_entry", ", ".join(missing))
    for entry in entries:
        _check_anchor(entry, loaded.base)
        _check_kind(entry, loaded.manuscript)
        _check_status(entry, loaded.manuscript)


def _required_items(manuscript: Manuscript) -> set[str]:
    items: set[str] = set()
    table_index = 0
    for block in manuscript.blocks:
        match block:
            case EquationBlock(lines=lines):
                for line in lines:
                    items.update(f"eq:{number}" for number in EQ_NUMBER_RE.findall(line))
            case FigureBlock(id=fig_id):
                items.add(f"fig:{fig_id}")
            case TableBlock():
                table_index += 1
                items.add(f"table:{table_index}")
            case HeadingBlock() | ParagraphBlock():
                pass
            case unreachable:
                assert_never(unreachable)
    return items


def _anchor_path(entry: LedgerEntry) -> str:
    match entry.checked_against:
        case PdfAnchor(pdf=token):
            return token
        case FileAnchor(file=token):
            return token
        case unreachable:
            assert_never(unreachable)


def _check_anchor(entry: LedgerEntry, base: Path) -> None:
    token = _anchor_path(entry)
    if not _file_exists(token, base):
        raise ManuscriptError("missing_source_file", token)


def _check_kind(entry: LedgerEntry, manuscript: Manuscript) -> None:
    match entry.kind:
        case LedgerKind.LITERATURE | LedgerKind.ADAPTED:
            if not _citation_matches(entry.citation, manuscript):
                raise ManuscriptError("missing_reference", entry.item)
        case LedgerKind.DERIVED | LedgerKind.MEASURED | LedgerKind.CONVENTION | LedgerKind.CONCEPT:
            return
        case unreachable:
            assert_never(unreachable)


def _citation_matches(citation: str, manuscript: Manuscript) -> bool:
    for ref in manuscript.references:
        cite = ref.cite
        if cite is not None and len(cite) >= _MIN_CITE and any(char.isalpha() for char in cite) and cite in citation:
            return True
        if f"[{ref.key}]" in citation:
            return True
    return False


def _check_status(entry: LedgerEntry, manuscript: Manuscript) -> None:
    match entry.status:
        case LedgerStatus.VERIFIED:
            return
        case LedgerStatus.UNVERIFIED:
            sources = _sources_for(entry, manuscript)
            if not sources or not all(_admits_unverified(source) for source in sources):
                raise ManuscriptError("unverified_claimed", entry.item)
        case unreachable:
            assert_never(unreachable)


def _admits_unverified(text: str) -> bool:
    return any(marker in text for marker in UNVERIFIED)


def _sources_for(entry: LedgerEntry, manuscript: Manuscript) -> list[str]:
    kind, rest = _split_item(entry.item)
    match kind:
        case ItemKind.EQ:
            return _equation_sources(manuscript, rest)
        case ItemKind.FIG:
            return _one(_figure_source(manuscript, rest))
        case ItemKind.TABLE:
            return _one(_table_source(manuscript, int(rest)))
        case ItemKind.CLAIM:
            return _one(_claim_prose(manuscript, entry.citation))
        case unreachable:
            assert_never(unreachable)


def _split_item(item: str) -> tuple[ItemKind, str]:
    prefix, _, rest = item.partition(":")
    try:
        kind = ItemKind(prefix)
    except ValueError:
        raise ManuscriptError("malformed_manuscript", "ledger item") from None
    return kind, rest


def _one(text: str | None) -> list[str]:
    return [] if text is None else [text]


def _equation_sources(manuscript: Manuscript, number: str) -> list[str]:
    token = f"({number})"
    found: list[str] = []
    for block in manuscript.blocks:
        match block:
            case EquationBlock(lines=lines, source=source):
                if any(token in line for line in lines):
                    found.append(source)
            case HeadingBlock() | ParagraphBlock() | TableBlock() | FigureBlock():
                pass
            case unreachable:
                assert_never(unreachable)
    return found


def _figure_source(manuscript: Manuscript, fig_id: str) -> str | None:
    for block in manuscript.blocks:
        match block:
            case FigureBlock(id=found, source=source):
                if found == fig_id:
                    return source
            case HeadingBlock() | ParagraphBlock() | EquationBlock() | TableBlock():
                pass
            case unreachable:
                assert_never(unreachable)
    return None


def _table_source(manuscript: Manuscript, number: int) -> str | None:
    seen = 0
    for block in manuscript.blocks:
        match block:
            case TableBlock(source=source):
                seen += 1
                if seen == number:
                    return source
            case HeadingBlock() | ParagraphBlock() | EquationBlock() | FigureBlock():
                pass
            case unreachable:
                assert_never(unreachable)
    return None


def _claim_prose(manuscript: Manuscript, citation: str) -> str | None:
    for block in manuscript.blocks:
        match block:
            case ParagraphBlock(text=text):
                if citation in text:
                    return text
            case HeadingBlock(text=text):
                if citation in text:
                    return text
            case FigureBlock(caption=text):
                if citation in text:
                    return text
            case EquationBlock() | TableBlock():
                pass
            case unreachable:
                assert_never(unreachable)
    return None
