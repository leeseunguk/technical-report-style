"""XML assertions for the style contract. Not a second CLI."""

from __future__ import annotations

import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_WIDTH_EMU = 5_436_000
MAX_HEIGHT_EMU = 6_120_000


def assert_geometry(blob: bytes) -> None:
    """Letter page and the measured margins."""
    sect = ET.fromstring(blob).find(f"{W}body/{W}sectPr")
    assert sect is not None
    page = _child(sect, "pgSz")
    margin = _child(sect, "pgMar")
    assert _attr(page, "w") == "12240" and _attr(page, "h") == "15840"
    assert _attr(margin, "top") == "1440" and _attr(margin, "bottom") == "1440"
    assert _attr(margin, "left") == "1800" and _attr(margin, "right") == "1800"
    assert _attr(margin, "header") == "720" and _attr(margin, "footer") == "720"


def assert_style(blob: bytes) -> None:
    """Direct formatting from the approved continuation, with inherited headings."""
    heading = find_paragraph(blob, "H1TOKEN")
    assert _attr(_child(heading.find(f"{W}pPr"), "pStyle"), "val") == "Heading1"
    assert heading.find(f".//{W}sz") is None
    caption = find_paragraph(blob, "Figure W.")
    cap = caption.find(f"{W}pPr")
    assert cap is not None and cap.find(f"{W}pStyle") is None
    assert _attr(_child(cap, "jc"), "val") == "center"
    assert _attr(_child(cap, "spacing"), "after") == "160"
    run = caption.find(f"{W}r/{W}rPr")
    assert run is not None and run.find(f"{W}i") is not None
    assert _attr(_child(run, "sz"), "val") == "18" and _attr(_child(run, "color"), "val") == "444444"
    picture = previous_of(blob, "Figure W.")
    assert picture.find(f"{W}pPr/{W}keepNext") is not None
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
    assert _attr(_child(equation.find(f"{W}r/{W}rPr"), "sz"), "val") == "22"
    assert equation.find(".//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath") is None
    body = find_paragraph(blob, "Body mentions Figure W")
    assert _attr(_child(body.find(f"{W}pPr"), "spacing"), "after") == "160"
    table = ET.fromstring(blob).find(f".//{W}tbl/{W}tblPr")
    assert table is not None and _attr(_child(table, "tblStyle"), "val") == "LightGrid-Accent1"
    assert _attr(_child(find_paragraph(blob, "HCOL").find(f"{W}r/{W}rPr"), "sz"), "val") == "18"


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
