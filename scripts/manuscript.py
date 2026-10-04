"""Parse a manuscript JSON file into a typed document."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final, Literal, assert_never

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from errors import ManuscriptError

KEY_PATTERN: Final = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,64}$"
CITATION_RE: Final = re.compile(r"(?<![\w\]])\[([A-Za-z0-9][A-Za-z0-9._:-]{0,64})\]")
LATEX_MARKERS: Final = ("\\", "$$")


class FrozenModel(BaseModel):
    """JSON objects are immutable after the boundary parse."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class HeadingBlock(FrozenModel):
    type: Literal["h"]
    level: int = Field(ge=1, le=9)
    text: str = Field(min_length=1)


class ParagraphBlock(FrozenModel):
    type: Literal["p"]
    text: str = Field(min_length=1)


class EquationBlock(FrozenModel):
    type: Literal["eq"]
    lines: list[str] = Field(min_length=1)


class TableBlock(FrozenModel):
    type: Literal["table"]
    headers: list[str] = Field(min_length=1)
    rows: list[list[str]]


class FigureBlock(FrozenModel):
    type: Literal["figure"]
    id: str = Field(min_length=1, pattern=KEY_PATTERN)
    mention: str = Field(min_length=1)
    asset: str = Field(min_length=1, pattern=KEY_PATTERN)
    caption: str = Field(min_length=1)
    source: str = Field(min_length=3)


class Asset(FrozenModel):
    path: str = Field(min_length=1)


class ReferenceEntry(FrozenModel):
    key: str = Field(min_length=1, pattern=KEY_PATTERN)
    text: str = Field(min_length=1)


class HeadingSpec(FrozenModel):
    level: int = Field(ge=1, le=9)
    text: str = Field(min_length=1)


Block = Annotated[
    HeadingBlock | ParagraphBlock | EquationBlock | TableBlock | FigureBlock,
    Field(discriminator="type"),
]


class Manuscript(FrozenModel):
    blocks: list[Block] = Field(min_length=1)
    references: list[ReferenceEntry] = Field(default_factory=list)
    assets: dict[str, Asset] = Field(default_factory=dict)
    reference_heading: HeadingSpec | None = None


@dataclass(frozen=True, slots=True)
class LoadedManuscript:
    """Manuscript plus the asset files the boundary resolved."""

    manuscript: Manuscript
    base: Path
    assets: dict[str, Path]


def schema_detail(exc: ValidationError) -> str:
    """Return locations and error types without echoing manuscript prose."""
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err["loc"]) or "<root>"
        parts.append(f"{loc}: {err['type']}")
    return "; ".join(parts[:8])


def load_manuscript(path: Path) -> LoadedManuscript:
    """Parse and check one manuscript. This is the only JSON boundary."""
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ManuscriptError("malformed_manuscript", "not utf-8") from None
    except OSError:
        raise ManuscriptError("malformed_manuscript", path.name) from None
    try:
        manuscript = Manuscript.model_validate_json(raw)
    except ValidationError as exc:
        raise ManuscriptError("malformed_manuscript", schema_detail(exc)) from None
    assets = validate_manuscript(manuscript, path.parent)
    return LoadedManuscript(manuscript=manuscript, base=path.parent, assets=assets)


def rendered_strings(manuscript: Manuscript) -> list[str]:
    """Text the renderer will place in the document."""
    found: list[str] = []
    for block in manuscript.blocks:
        match block:
            case HeadingBlock(text=text) | ParagraphBlock(text=text):
                found.append(text)
            case EquationBlock(lines=lines):
                found.extend(lines)
            case TableBlock(headers=headers, rows=rows):
                found.extend(headers)
                for row in rows:
                    found.extend(row)
            case FigureBlock(caption=caption):
                found.append(caption)
            case unreachable:
                assert_never(unreachable)
    heading = manuscript.reference_heading
    if heading is not None:
        found.append(heading.text)
    found.extend(ref.text for ref in manuscript.references)
    return found


def paragraph_text(block: Block) -> str | None:
    """Return paragraph text, or None for every other block."""
    match block:
        case ParagraphBlock(text=text):
            return text
        case HeadingBlock() | EquationBlock() | TableBlock() | FigureBlock():
            return None
        case unreachable:
            assert_never(unreachable)


def heading_levels(manuscript: Manuscript) -> set[int]:
    """Heading levels the source document must already define."""
    levels: set[int] = set()
    for block in manuscript.blocks:
        match block:
            case HeadingBlock(level=level):
                levels.add(level)
            case ParagraphBlock() | EquationBlock() | TableBlock() | FigureBlock():
                pass
            case unreachable:
                assert_never(unreachable)
    heading = manuscript.reference_heading
    if heading is not None:
        levels.add(heading.level)
    return levels


def has_table(manuscript: Manuscript) -> bool:
    """Report whether the manuscript places a table."""
    for block in manuscript.blocks:
        match block:
            case TableBlock():
                return True
            case HeadingBlock() | ParagraphBlock() | EquationBlock() | FigureBlock():
                pass
            case unreachable:
                assert_never(unreachable)
    return False


def figure_count(manuscript: Manuscript) -> int:
    """Count figure blocks."""
    total = 0
    for block in manuscript.blocks:
        match block:
            case FigureBlock():
                total += 1
            case HeadingBlock() | ParagraphBlock() | EquationBlock() | TableBlock():
                pass
            case unreachable:
                assert_never(unreachable)
    return total


def validate_manuscript(manuscript: Manuscript, base: Path) -> dict[str, Path]:
    """Apply mention, caption, source, citation, and file checks."""
    _check_keys(manuscript)
    resolved = _resolve_assets(manuscript, base)
    _check_blocks(manuscript, resolved)
    _check_references(manuscript)
    return resolved


def _reject_latex(texts: list[str]) -> None:
    for text in texts:
        if any(marker in text for marker in LATEX_MARKERS):
            raise ManuscriptError("latex_marker", "editable linear text only")


def _check_keys(manuscript: Manuscript) -> None:
    for key in manuscript.assets:
        if re.fullmatch(KEY_PATTERN, key) is None:
            raise ManuscriptError("malformed_manuscript", "asset key")
    keys = [ref.key for ref in manuscript.references]
    if len(keys) != len(set(keys)):
        raise ManuscriptError("malformed_manuscript", "duplicate reference key")


def _resolve_assets(manuscript: Manuscript, base: Path) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for key, asset in manuscript.assets.items():
        raw = Path(asset.path)
        path = raw if raw.is_absolute() else base / raw
        resolved[key] = path.resolve()
    return resolved


def _check_blocks(manuscript: Manuscript, assets: dict[str, Path]) -> None:
    used: set[str] = set()
    figure_ids: set[str] = set()
    for index, block in enumerate(manuscript.blocks):
        match block:
            case FigureBlock() as figure:
                _check_figure(manuscript, index, figure, used, figure_ids, assets)
            case TableBlock() as table:
                _check_table(table)
            case EquationBlock(lines=lines):
                _reject_latex(lines)
                if any(line == "" for line in lines):
                    raise ManuscriptError("malformed_manuscript", "empty equation line")
            case HeadingBlock() | ParagraphBlock():
                pass
            case unreachable:
                assert_never(unreachable)


def _check_table(table: TableBlock) -> None:
    width = len(table.headers)
    for row in table.rows:
        if len(row) != width:
            raise ManuscriptError("malformed_manuscript", "table row width")


def _check_figure(
    manuscript: Manuscript,
    index: int,
    figure: FigureBlock,
    used: set[str],
    figure_ids: set[str],
    assets: dict[str, Path],
) -> None:
    if figure.id in figure_ids:
        raise ManuscriptError("malformed_manuscript", "duplicate figure id")
    figure_ids.add(figure.id)
    if figure.asset in used:
        raise ManuscriptError("malformed_manuscript", "duplicate figure asset")
    used.add(figure.asset)
    if figure.asset not in assets:
        raise ManuscriptError("missing_figure", figure.asset)
    if figure.id not in figure.mention or figure.mention not in figure.caption:
        raise ManuscriptError("missing_figure_mention", figure.id)
    if figure.source not in figure.caption:
        raise ManuscriptError("missing_figure_source", figure.id)
    previous = manuscript.blocks[index - 1] if index else None
    text = None if previous is None else paragraph_text(previous)
    if text is None or figure.mention not in text:
        raise ManuscriptError("missing_figure_mention", figure.id)
    path = assets[figure.asset]
    if not path.is_file():
        raise ManuscriptError("missing_figure", str(path))
    try:
        with Image.open(path) as image:
            image.load()
    except FileNotFoundError:
        raise ManuscriptError("missing_figure", str(path)) from None
    except (UnidentifiedImageError, OSError):
        raise ManuscriptError("malformed_figure", str(path)) from None


def _check_references(manuscript: Manuscript) -> None:
    known = {ref.key for ref in manuscript.references}
    cited: set[str] = set()
    found: set[str] = set()
    for text in rendered_strings(manuscript):
        found.update(CITATION_RE.findall(text))
    for block in manuscript.blocks:
        text = paragraph_text(block)
        if text is not None:
            cited.update(CITATION_RE.findall(text))
    missing = sorted(found - known)
    if missing:
        joined = ", ".join(missing)
        raise ManuscriptError("missing_reference", joined)
    uncited = sorted(known - cited)
    if uncited:
        joined = ", ".join(uncited)
        raise ManuscriptError("missing_reference", joined)
