"""Place generic blocks using the approved continuation's direct formatting."""

from __future__ import annotations

from pathlib import Path
from typing import Final, assert_never

from docx.document import Document as DocumentType
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Emu, Pt, RGBColor
from docx.text.paragraph import Paragraph
from PIL import Image

from errors import PackageError
from manuscript import (
    EquationBlock,
    FigureBlock,
    HeadingBlock,
    LoadedManuscript,
    ParagraphBlock,
    TableBlock,
    has_table,
    heading_levels,
)

CONTENT_WIDTH_CM: Final = 15.1
MAX_HEIGHT_CM: Final = 17.0
EMU_PER_CM: Final = 360_000
MAX_WIDTH_EMU: Final = round(CONTENT_WIDTH_CM * EMU_PER_CM)
MAX_HEIGHT_EMU: Final = round(MAX_HEIGHT_CM * EMU_PER_CM)
TABLE_STYLE: Final = "Light Grid Accent 1"
CAPTION_COLOR: Final = RGBColor(0x44, 0x44, 0x44)
BODY_AFTER_PT: Final = 8
CAPTION_PT: Final = 9
EQUATION_PT: Final = 11
TABLE_PT: Final = 9


def render(document: DocumentType, loaded: LoadedManuscript) -> None:
    """Append the manuscript to an open document. Does not save or clear."""
    require_styles(document, loaded)
    for block in loaded.manuscript.blocks:
        match block:
            case HeadingBlock(text=text, level=level):
                add_heading(document, text, level)
            case ParagraphBlock(text=text):
                add_paragraph(document, text)
            case EquationBlock(lines=lines):
                add_equation(document, lines)
            case TableBlock(headers=headers, rows=rows):
                add_table(document, headers, rows)
            case FigureBlock() as figure:
                add_figure(document, figure_path(loaded, figure), figure.caption)
            case unreachable:
                assert_never(unreachable)
    heading = loaded.manuscript.reference_heading
    if heading is not None:
        add_heading(document, heading.text, heading.level)
    for ref in loaded.manuscript.references:
        paragraph = add_paragraph(document, ref.text)
        paragraph.paragraph_format.keep_together = True


def require_styles(document: DocumentType, loaded: LoadedManuscript) -> None:
    """Fail if the source is missing a heading or table style the manuscript uses."""
    names = {style.name for style in document.styles}
    for level in heading_levels(loaded.manuscript):
        name = f"Heading {level}"
        if name not in names:
            raise PackageError("missing_heading_style", name)
    if has_table(loaded.manuscript) and TABLE_STYLE not in names:
        raise PackageError("missing_table_style", TABLE_STYLE)


def picture_emu(path: Path) -> tuple[int, int]:
    """Return width and height in EMU inside 15.1 cm by 17 cm, preserving pixels."""
    with Image.open(path) as image:
        width_px, height_px = image.size
    if width_px < 1 or height_px < 1:
        raise PackageError("malformed_figure", path.name)
    width = MAX_WIDTH_EMU
    height = round(width * height_px / width_px)
    if height > MAX_HEIGHT_EMU:
        height = MAX_HEIGHT_EMU
        width = round(height * width_px / height_px)
    return width, height


def add_heading(document: DocumentType, text: str, level: int) -> None:
    """Use the source heading style with no direct size override."""
    try:
        document.add_heading(text, level=level)
    except KeyError:
        raise PackageError("missing_heading_style", str(level)) from None


def add_paragraph(document: DocumentType, text: str) -> Paragraph:
    """Body paragraph: inherited 11 pt, direct 8 pt space after."""
    paragraph = document.add_paragraph()
    add_run(paragraph, text)
    paragraph.paragraph_format.space_after = Pt(BODY_AFTER_PT)
    return paragraph


def add_equation(document: DocumentType, lines: list[str]) -> None:
    """Centered editable text, 11 pt italic. Not an OMML equation."""
    last = len(lines) - 1
    for index, line in enumerate(lines):
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_run(paragraph, line, size=EQUATION_PT, italic=True)
        paragraph.paragraph_format.space_before = Pt(1)
        paragraph.paragraph_format.space_after = Pt(1)
        if index != last:
            paragraph.paragraph_format.keep_with_next = True


def add_table(document: DocumentType, headers: list[str], rows: list[list[str]]) -> None:
    """Light Grid Accent 1, 9 pt. The style must already exist."""
    try:
        table = document.add_table(rows=1, cols=len(headers))
        table.style = TABLE_STYLE
    except KeyError:
        raise PackageError("missing_table_style", TABLE_STYLE) from None
    table.autofit = True
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = ""
        add_run(cell.paragraphs[0], header, size=TABLE_PT, bold=True)
    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = ""
            add_run(cells[index].paragraphs[0], value, size=TABLE_PT)
    spacer = document.add_paragraph()
    spacer.paragraph_format.space_after = Pt(6)


def add_figure(document: DocumentType, path: Path, caption: str) -> None:
    """Picture and caption stay together. Caption is not the Caption style."""
    if not path.is_file():
        raise PackageError("missing_figure", str(path))
    width, height = picture_emu(path)
    picture = document.add_paragraph()
    picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
    picture.paragraph_format.space_before = Pt(8)
    picture.paragraph_format.space_after = Pt(2)
    picture.add_run().add_picture(str(path), width=Emu(width), height=Emu(height))
    picture.paragraph_format.keep_with_next = True
    cap = document.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_before = Pt(0)
    cap.paragraph_format.space_after = Pt(BODY_AFTER_PT)
    cap.paragraph_format.keep_together = True
    add_run(cap, caption, size=CAPTION_PT, italic=True, color=CAPTION_COLOR)


def add_run(
    paragraph: Paragraph,
    text: str,
    *,
    size: float | None = None,
    italic: bool = False,
    bold: bool = False,
    color: RGBColor | None = None,
) -> None:
    """Direct run formatting. Unset size inherits the paragraph or document default."""
    run = paragraph.add_run(text)
    run.italic = italic
    run.bold = bold
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color


def figure_path(loaded: LoadedManuscript, figure: FigureBlock) -> Path:
    """Return the resolved asset path recorded at the boundary."""
    path = loaded.assets.get(figure.asset)
    if path is None:
        raise PackageError("missing_figure", figure.asset)
    return path
