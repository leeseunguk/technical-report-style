"""Editable Office Math. A conversion source is consumed and never copied into the document."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Final

from lxml import etree

from errors import PackageError

MATH_NS: Final = "http://schemas.openxmlformats.org/officeDocument/2006/math"
XML_SPACE: Final = "{http://www.w3.org/XML/1998/namespace}space"
_LEADING_NUMBER: Final = re.compile(r"\((\d+)\)\s+.+")
_TRAILING_NUMBER: Final = re.compile(r".+\s+\((\d+)\)")
Converter = Callable[[str], str]


def equation_math(line: str, latex: str | None) -> etree._Element:
    """One native equation. Without latex, the line text is preserved exactly."""
    if latex is None:
        return _literal(line)
    return _with_number(_from_latex(latex), line)


def equation_xml(line: str, latex: str | None) -> str:
    """Office Math markup for one line. The conversion source is not included."""
    return etree.tostring(equation_math(line, latex), encoding=str)


def complete_math_arguments(root: etree._Element) -> int:
    """Complete square-root degrees and hide intentionally empty n-ary limits."""
    count = 0
    for radical in root.findall(f".//{{{MATH_NS}}}rad"):
        if radical.find(f"{{{MATH_NS}}}deg") is not None:
            continue
        expression = radical.find(f"{{{MATH_NS}}}e")
        if expression is None:
            raise ValueError("Square root has no radicand")
        properties = radical.find(f"{{{MATH_NS}}}radPr")
        if properties is None:
            properties = etree.Element(f"{{{MATH_NS}}}radPr")
            radical.insert(0, properties)
        hidden = etree.SubElement(properties, f"{{{MATH_NS}}}degHide")
        hidden.set(f"{{{MATH_NS}}}val", "1")
        radical.insert(radical.index(expression), etree.Element(f"{{{MATH_NS}}}deg"))
        count += 1
    for operator in root.findall(f".//{{{MATH_NS}}}nary"):
        properties = operator.find(f"{{{MATH_NS}}}naryPr")
        if properties is None:
            properties = etree.Element(f"{{{MATH_NS}}}naryPr")
            operator.insert(0, properties)
        for name in ("sub", "sup"):
            limit = operator.find(f"{{{MATH_NS}}}{name}")
            if limit is None or any(limit.itertext()):
                continue
            flag = properties.find(f"{{{MATH_NS}}}{name}Hide")
            if flag is None:
                flag = etree.SubElement(properties, f"{{{MATH_NS}}}{name}Hide")
                flag.set(f"{{{MATH_NS}}}val", "1")
                count += 1
    return count


def _converters() -> tuple[Converter, Converter]:
    try:
        from latex2mathml.converter import convert as to_mathml
        from mathml2omml import convert as to_omml
    except ImportError as exc:
        raise PackageError("missing_math_dependency", exc.name or "math") from None
    return to_mathml, to_omml


def _from_latex(latex: str) -> etree._Element:
    to_mathml, to_omml = _converters()
    try:
        raw = to_omml(to_mathml(latex))
        wrapper = etree.fromstring(f'<root xmlns:m="{MATH_NS}">{raw}</root>'.encode())
    except Exception:
        raise ValueError("conversion failed") from None
    if len(wrapper) != 1 or wrapper[0].tag != f"{{{MATH_NS}}}oMath":
        raise ValueError("conversion failed")
    _ = complete_math_arguments(wrapper[0])
    _require_complete(wrapper[0])
    return wrapper[0]


def _require_complete(root: etree._Element) -> None:
    if "\\" in "".join(root.itertext()):
        raise ValueError("conversion failed")
    for radical in root.findall(f".//{{{MATH_NS}}}rad"):
        degree = radical.find(f"{{{MATH_NS}}}deg")
        expression = radical.find(f"{{{MATH_NS}}}e")
        if degree is None or expression is None or not _has_text(expression):
            raise ValueError("conversion failed")
    for operator in root.findall(f".//{{{MATH_NS}}}nary"):
        properties = operator.find(f"{{{MATH_NS}}}naryPr")
        for name in ("sub", "sup"):
            limit = operator.find(f"{{{MATH_NS}}}{name}")
            if limit is None or any(limit.itertext()):
                continue
            flag = None if properties is None else properties.find(f"{{{MATH_NS}}}{name}Hide")
            value = None if flag is None else flag.get(f"{{{MATH_NS}}}val")
            if value != "1":
                raise ValueError("conversion failed")


def _has_text(node: etree._Element) -> bool:
    return any(text.strip() for text in node.itertext() if text)


def _literal(text: str) -> etree._Element:
    omath = etree.Element(f"{{{MATH_NS}}}oMath", nsmap={"m": MATH_NS})
    omath.append(_plain_run(text))
    return omath


def _with_number(omath: etree._Element, line: str) -> etree._Element:
    stripped = line.strip()
    leading = _LEADING_NUMBER.fullmatch(stripped)
    parent = _content_parent(omath)
    if leading is not None:
        parent.insert(0, _plain_run(f"({leading.group(1)})\u2001\u2001"))
        return omath
    trailing = _TRAILING_NUMBER.fullmatch(stripped)
    if trailing is not None:
        parent.append(_plain_run(f"\u2001\u2001({trailing.group(1)})"))
    return omath


def _content_parent(omath: etree._Element) -> etree._Element:
    box = omath.find(f"{{{MATH_NS}}}box")
    if box is not None:
        expression = box.find(f"{{{MATH_NS}}}e")
        if expression is not None:
            return expression
    return omath


def _plain_run(text: str) -> etree._Element:
    run = etree.Element(f"{{{MATH_NS}}}r")
    props = etree.SubElement(run, f"{{{MATH_NS}}}rPr")
    style = etree.SubElement(props, f"{{{MATH_NS}}}sty")
    style.set(f"{{{MATH_NS}}}val", "p")
    node = etree.SubElement(run, f"{{{MATH_NS}}}t")
    node.set(XML_SPACE, "preserve")
    node.text = text
    return run
