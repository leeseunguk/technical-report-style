"""XML assertions for the style contract. Not a second CLI."""

from __future__ import annotations

import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_WIDTH_EMU = 5_580_000
MAX_HEIGHT_EMU = 6_120_000


def assert_geometry(blob: bytes) -> None:
    """A4 page and the measured textbook margins."""
    sect = ET.fromstring(blob).find(f"{W}body/{W}sectPr")
    assert sect is not None
    page = _child(sect, "pgSz")
    margin = _child(sect, "pgMar")
    assert _attr(page, "w") == "11906" and _attr(page, "h") == "16838"
    assert _attr(margin, "top") == "1417" and _attr(margin, "bottom") == "1417"
    assert _attr(margin, "left") == "1417" and _attr(margin, "right") == "1417"
    assert _attr(margin, "header") == "709" and _attr(margin, "footer") == "709"


def assert_style(blob: bytes) -> None:
    """Textbook styles: black headings, Caption, Table, inherited body size."""
    heading = find_paragraph(blob, "H1TOKEN")
    assert _attr(_child(heading.find(f"{W}pPr"), "pStyle"), "val") == "Heading1"
    assert heading.find(f".//{W}sz") is None
    caption = find_paragraph(blob, "Figure W.")
    cap = caption.find(f"{W}pPr")
    assert cap is not None
    assert _attr(_child(cap, "pStyle"), "val") == "Caption"
    assert _attr(_child(cap, "jc"), "val") == "center"
    run = caption.find(f"{W}r/{W}rPr")
    assert run is not None and _false_flag(run, "i")
    assert run.find(f"{W}sz") is None and run.find(f"{W}color") is None
    picture = previous_of(blob, "Figure W.")
    assert picture.find(f"{W}pPr/{W}keepNext") is not None
    spacing = _child(picture.find(f"{W}pPr"), "spacing")
    assert _attr(spacing, "before") == "80" and _attr(spacing, "after") == "40"
    extent = picture.find(".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent")
    assert extent is not None
    cx, cy = int(extent.get("cx", "0")), int(extent.get("cy", "0"))
    assert cx == MAX_WIDTH_EMU and cy <= MAX_HEIGHT_EMU
    assert abs(cx * 500 - cy * 2000) <= 2000
    tall = previous_of(blob, "tall-source-token")
    assert tall is not None
    tall_extent = tall.find(".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent")
    assert tall_extent is not None
    tcx, tcy = int(tall_extent.get("cx", "0")), int(tall_extent.get("cy", "0"))
    assert tcy == MAX_HEIGHT_EMU and tcx <= MAX_WIDTH_EMU
    equation = find_paragraph(blob, "EQTOKEN")
    assert _attr(_child(equation.find(f"{W}pPr"), "jc"), "val") == "center"
    assert _attr(_child(equation.find(f"{W}r/{W}rPr"), "sz"), "val") == "21"
    assert equation.find(".//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath") is None
    body = find_paragraph(blob, "Body mentions Figure W")
    assert _attr(_child(body.find(f"{W}pPr"), "pStyle"), "val") == "BodyText"
    direct = body.find(f"{W}pPr/{W}spacing")
    assert direct is None or _attr(direct, "after") != "160"
    table = ET.fromstring(blob).find(f".//{W}tbl/{W}tblPr")
    assert table is not None and _attr(_child(table, "tblStyle"), "val") == "Table"
    header = find_paragraph(blob, "HCOL").find(f"{W}r/{W}rPr")
    assert header is not None and header.find(f"{W}b") is not None and header.find(f"{W}sz") is None


def prefix_preserved(source_xml: bytes, output_xml: bytes) -> bool:
    """Body-child prefix check used by the append test."""
    old, new = _kids(source_xml), _kids(output_xml)
    return len(new) >= len(old) and new[: len(old)] == old


def previous_of(blob: bytes, token: str) -> ET.Element:
    """Return the paragraph immediately before the one containing token."""
    root = ET.fromstring(blob)
    previous: ET.Element | None = None
    for el in root.iter(f"{W}p"):
        if token in "".join(el.itertext()):
            assert previous is not None
            return previous
        previous = el
    raise AssertionError(token)


def find_paragraph(blob: bytes, token: str) -> ET.Element:
    root = ET.fromstring(blob)
    found = [el for el in root.findall(f".//{W}p") if token in "".join(el.itertext())]
    assert len(found) == 1
    return found[0]


def _kids(blob: bytes) -> list[bytes]:
    body = ET.fromstring(blob).find(f"{W}body")
    assert body is not None
    children = list(body)
    if children and children[-1].tag == f"{W}sectPr":
        children = children[:-1]
    return [ET.tostring(child) for child in children]


def _child(el: ET.Element | None, name: str) -> ET.Element:
    assert el is not None
    found = el.find(f"{W}{name}")
    assert found is not None
    return found


def _attr(el: ET.Element, name: str) -> str:
    value = el.get(f"{W}{name}")
    assert isinstance(value, str)
    return value


def _false_flag(el: ET.Element, name: str) -> bool:
    found = el.find(f"{W}{name}")
    if found is None:
        return False
    return found.get(f"{W}val") in {"0", "false", "False"}
