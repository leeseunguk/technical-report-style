"""Place generic blocks with the textbook style source, not the old Letter continuation."""

from __future__ import annotations

from pathlib import Path
from typing import Final, assert_never

from docx.document import Document as DocumentType
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Pt, RGBColor
from docx.table import Table
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

FIGURE_WIDTH_CM: Final = 15.5
FIGURE_HEIGHT_CM: Final = 17.0
EMU_PER_CM: Final = 360_000
MAX_HEIGHT_EMU: Final = round(FIGURE_HEIGHT_CM * EMU_PER_CM)
CAPTION_PT: Final = 9.5
CAPTION_COLOR: Final = RGBColor(0x22, 0x22, 0x22)
EQUATION_PT: Final = 10.5
TABLE_STYLE_CANDIDATES: Final = ("Table", "Light Grid Accent 1")


def render(document: DocumentType, loaded: LoadedManuscript) -> None:
    """Append the manuscript to an open document. Does not save or clear."""
    require_styles(document, loaded)
    for block in loaded.manuscript.blocks:
        match block:
            case HeadingBlock(text=text, level=level):
                add_heading(document, text, level)
            case ParagraphBlock(text=text, role=role):
                match role:
                    case "body":
                        add_paragraph(document, text)
                    case "callout-title" | "callout-body":
                        name = resolve_named_style(document, "BlockText", "Block Text")
                        if name is None:
                            raise PackageError("missing_callout_style", "Block Text")
                        paragraph = document.add_paragraph(style=name)
                        add_run(paragraph, text, bold=role == "callout-title")
                        paragraph.paragraph_format.keep_together = True
                        if role == "callout-title":
                            paragraph.paragraph_format.keep_with_next = True
                    case unreachable_role:
                        assert_never(unreachable_role)
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
    for level in heading_levels(loaded.manuscript):
        if heading_style(document, level) is None:
            raise PackageError("missing_heading_style", f"Heading {level}")
    if has_table(loaded.manuscript) and table_style(document) is None:
        raise PackageError("missing_table_style", TABLE_STYLE_CANDIDATES[0])


def resolve_style(document: DocumentType, *candidates: str) -> tuple[str, str] | None:
    """Return a defined source style name and style id."""
    styles = [style for style in document.styles if getattr(style, "element", None) is not None]
    for candidate in candidates:
        for style in styles:
            style_id = getattr(style, "style_id", None)
            name = style.name
            if not isinstance(name, str) or not isinstance(style_id, str):
                continue
            if style_id == candidate or name == candidate or name.lower() == candidate.lower():
                return name, style_id
    return None


def resolve_named_style(document: DocumentType, *candidates: str) -> str | None:
    """Return a defined source style name, preferring style id, then exact name."""
    found = resolve_style(document, *candidates)
    return None if found is None else found[0]


def heading_style(document: DocumentType, level: int) -> str | None:
    """Heading style id or UI name. Pandoc stores the textbook name as 'heading 1'."""
    return resolve_named_style(document, f"Heading{level}", f"Heading {level}", f"heading {level}")


def table_style(document: DocumentType) -> tuple[str, str] | None:
    """Textbook Table style, or Light Grid Accent 1 when that is what the source has."""
    return resolve_style(document, *TABLE_STYLE_CANDIDATES)


def body_style(document: DocumentType) -> str | None:
    """Textbook Body Text when present, otherwise Normal."""
    return resolve_named_style(document, "Body Text", "Normal")


def content_width_emu(document: DocumentType) -> int:
    """15.5 cm textbook cap, narrowed to the source section content width."""
    cap = round(FIGURE_WIDTH_CM * EMU_PER_CM)
    section = document.sections[-1]
    page = section.page_width
    left = section.left_margin
    right = section.right_margin
    if page is None or left is None or right is None:
        return cap
    content = int(page) - int(left) - int(right)
    if content < 1:
        return cap
    return min(cap, content)


def picture_emu(path: Path, max_width: int) -> tuple[int, int]:
    """Return width and height in EMU inside the width cap by 17 cm."""
    with Image.open(path) as image:
        width_px, height_px = image.size
    if width_px < 1 or height_px < 1:
        raise PackageError("malformed_figure", path.name)
    width = max_width
    height = round(width * height_px / width_px)
    if height > MAX_HEIGHT_EMU:
        height = MAX_HEIGHT_EMU
        width = round(height * width_px / height_px)
    return width, height


def add_heading(document: DocumentType, text: str, level: int) -> None:
    """Use the source heading style. Do not override its size or color."""
    name = heading_style(document, level)
    if name is None:
        raise PackageError("missing_heading_style", f"Heading {level}")
    document.add_paragraph(text, style=name)


def add_paragraph(document: DocumentType, text: str) -> Paragraph:
    """Inherit 10.5 pt and line spacing 1.4. Do not force the old 8 pt space-after."""
    name = body_style(document)
    paragraph = document.add_paragraph(style=name) if name is not None else document.add_paragraph()
    add_run(paragraph, text)
    return paragraph


def add_equation(document: DocumentType, lines: list[str]) -> None:
    """Centered editable text at body size. Not an OMML equation."""
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
    """Source Table style and inherited cell size. Header text is bold."""
    resolved = table_style(document)
    if resolved is None:
        raise PackageError("missing_table_style", TABLE_STYLE_CANDIDATES[0])
    _name, style_id = resolved
    table = document.add_table(rows=1, cols=len(headers))
    # python-docx omits tblStyle when the style is the document default. The textbook writes it.
    _set_table_style(table, style_id)
    table.autofit = True
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = ""
        add_run(cell.paragraphs[0], header, bold=True)
    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = ""
            add_run(cells[index].paragraphs[0], value)


def _set_table_style(table: Table, style_id: str) -> None:
    """Write tblStyle even when the style is the package default."""
    tbl_pr = table._tbl.tblPr
    if tbl_pr is None:
        tbl_pr = OxmlElement("w:tblPr")
        table._tbl.insert(0, tbl_pr)
    element = tbl_pr.find(qn("w:tblStyle"))
    if element is None:
        element = OxmlElement("w:tblStyle")
        tbl_pr.insert(0, element)
    element.set(qn("w:val"), style_id)


def add_figure(document: DocumentType, path: Path, caption: str) -> None:
    """Centered picture kept with the caption. Caption is not 9 pt italic."""
    if not path.is_file():
        raise PackageError("missing_figure", str(path))
    width, height = picture_emu(path, content_width_emu(document))
    picture = document.add_paragraph()
    picture_name = body_style(document)
    if picture_name is not None:
        picture.style = picture_name
    picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
    picture.paragraph_format.space_before = Pt(4)
    picture.paragraph_format.space_after = Pt(2)
    picture.paragraph_format.line_spacing = 1.0
    picture.add_run().add_picture(str(path), width=Emu(width), height=Emu(height))
    picture.paragraph_format.keep_with_next = True
    add_caption(document, caption)


def add_caption(document: DocumentType, caption: str) -> None:
    """Use Caption when the source defines it. Fallback is 9.5 pt regular, not 9 pt italic."""
    name = resolve_named_style(document, "Caption")
    paragraph = document.add_paragraph(style=name) if name is not None else document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.keep_together = True
    if name is None:
        add_run(paragraph, caption, size=CAPTION_PT, italic=False, color=CAPTION_COLOR)
        return
    add_run(paragraph, caption, italic=False)


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
