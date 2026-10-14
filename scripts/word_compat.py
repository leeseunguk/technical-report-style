"""Word-compatibility gate for built packages.

Microsoft Word rejects packages that LibreOffice and python-docx accept
happily: unbound QName prefixes in attribute values, non-canonical ns0/ns1
prefixes left by stdlib ElementTree reserialization, out-of-order sectPr or
pPr children, a missing w:gutter on w:pgMar, dangling comments parts, and a
settings-level w:updateFields flag that pops a field-update prompt on open.
assert_word_compatible() fails the build before any of that reaches a user.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Final

from lxml import etree

from errors import PackageError

W_NS: Final = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W: Final = f"{{{W_NS}}}"
REL_NS: Final = "http://schemas.openxmlformats.org/package/2006/relationships"
MC_NS: Final = "http://schemas.openxmlformats.org/markup-compatibility/2006"
XSI_NS: Final = "http://www.w3.org/2001/XMLSchema-instance"

GENERATED_PREFIX: Final = re.compile(r"\bns\d+:")
QNAME_VALUE: Final = re.compile(r"\b([a-zA-Z_][\w.-]*):[\w.-]+\b")

SECTPR_ORDER: Final = [
    "headerReference", "footerReference", "footnotePr", "endnotePr", "type",
    "pgSz", "pgMar", "paperSrc", "pgBorders", "lnNumType", "pgNumType", "cols",
    "formProt", "vAlign", "noEndnote", "titlePg", "textDirection", "bidi",
    "rtlGutter", "docGrid", "printerSettings", "sectPrChange",
]
PPR_ORDER: Final = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
    "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs",
    "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
    "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
    "suppressOverlap", "jc", "textDirection", "textAlignment",
    "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr",
    "pPrChange",
]
RPR_ORDER: Final = [
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike",
    "dstrike", "outline", "shadow", "emboss", "imprint", "noProof",
    "snapToGrid", "vanish", "webHidden", "color", "spacing", "w", "kern",
    "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd",
    "fitText", "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout",
    "specVanish", "oMath",
]
TBLPR_ORDER: Final = [
    "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
    "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd",
    "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption",
    "tblDescription", "tblPrChange",
]
TRPR_ORDER: Final = [
    "cnfStyle", "divId", "gridBefore", "gridAfter", "wBefore", "wAfter",
    "cantSplit", "trHeight", "tblHeader", "tblCellSpacing", "jc", "hidden",
    "ins", "del", "trPrChange",
]
TCPR_ORDER: Final = [
    "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
    "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark",
    "headers", "cellIns", "cellDel", "cellMerge", "tcPrChange",
]
ORDER_MAP: Final = {
    "sectPr": SECTPR_ORDER, "pPr": PPR_ORDER, "rPr": RPR_ORDER,
    "tblPr": TBLPR_ORDER, "trPr": TRPR_ORDER, "tcPr": TCPR_ORDER,
}
SKIP_ATTRS: Final = frozenset({"xml", "xmlns", "xsi"})
QNAME_ATTRS: Final = frozenset({f"{{{XSI_NS}}}type", f"{{{MC_NS}}}Ignorable"})


def assert_word_compatible(path: Path) -> None:
    """Raise PackageError when the package would trip Word's strict reader."""
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        parts = {name: archive.read(name) for name in names}
    issues: list[str] = []
    for name, blob in parts.items():
        if not name.endswith((".xml", ".rels")):
            continue
        if GENERATED_PREFIX.search(blob.decode("utf-8", "replace")):
            issues.append(f"{name}: reserialized ns0-style prefixes")
        try:
            root = etree.fromstring(blob)
        except etree.XMLSyntaxError as exc:
            issues.append(f"{name}: malformed XML {exc}")
            continue
        issues.extend(_attr_prefix_issues(name, root))
        if name == "word/document.xml":
            issues.extend(_document_issues(root))
        if name == "word/styles.xml":
            issues.extend(_order_issues(name, root))
        if name == "word/settings.xml":
            for el in root.iter(f"{W}updateFields"):
                if (el.get(f"{W}val") or "true") != "false":
                    issues.append("settings.xml: w:updateFields prompts Word field warning")
        if name.endswith(".rels"):
            issues.extend(_rels_issues(name, root, names))
        if name == "[Content_Types].xml":
            issues.extend(_content_type_issues(root, names))
    if "word/comments.xml" in parts:
        issues.append("word/comments.xml present but comments are not emitted")
    if issues:
        raise PackageError("word_incompatible", "; ".join(sorted(set(issues))[:12]))


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _declared(el: etree._Element, prefix: str) -> bool:
    node: etree._Element | None = el
    while node is not None:
        if prefix in node.nsmap:
            return True
        node = node.getparent()
    return False


def _attr_prefix_issues(name: str, root: etree._Element) -> list[str]:
    """QName-valued attributes must resolve to a prefix declared in scope."""
    found: list[str] = []
    for el in root.iter():
        for key, value in el.attrib.items():
            if key not in QNAME_ATTRS:
                continue
            for token in value.split():
                if ":" not in token:
                    continue
                prefix = token.split(":", 1)[0]
                if prefix in SKIP_ATTRS or _declared(el, prefix):
                    continue
                found.append(f"{name}: unbound prefix {prefix} in @{_localname(key)}")
    return found


def _ordered(el: etree._Element, order: list[str]) -> list[str] | None:
    kids = [
        etree.QName(c).localname
        for c in el
        if isinstance(c.tag, str) and etree.QName(c).namespace == W_NS
    ]
    idx = [order.index(k) if k in order else len(order) for k in kids]
    return None if idx == sorted(idx) else kids


def _order_issues(name: str, root: etree._Element) -> list[str]:
    found: list[str] = []
    for el in root.iter():
        if not isinstance(el.tag, str) or etree.QName(el).namespace != W_NS:
            continue
        order = ORDER_MAP.get(etree.QName(el).localname)
        if order is None:
            continue
        bad = _ordered(el, order)
        if bad:
            found.append(f"{name}: <{_localname(el.tag)}> child order {'>'.join(bad)}")
    return found


def _document_issues(root: etree._Element) -> list[str]:
    found = _order_issues("word/document.xml", root)
    for el in root.iter(f"{W}pgMar"):
        if el.get(f"{W}gutter") is None:
            found.append("word/document.xml: w:pgMar missing required w:gutter")
    for el in root.iter(f"{W}pgSz"):
        if el.get(f"{W}w") is None or el.get(f"{W}h") is None:
            found.append("word/document.xml: w:pgSz missing w:w or w:h")
    return found


def _rels_issues(name: str, root: etree._Element, names: set[str]) -> list[str]:
    found: list[str] = []
    base = Path(name).parent.parent
    for rel in root:
        target = rel.get("Target") or ""
        if rel.get("TargetMode") == "External" or "://" in target:
            continue
        resolved = (base / target.lstrip("/")).as_posix()
        if resolved not in names:
            found.append(f"{name}: dangling target {target}")
    return found


def _content_type_issues(root: etree._Element, names: set[str]) -> list[str]:
    overrides = {o.get("PartName", "").lstrip("/") for o in root if _localname(o.tag) == "Override"}
    defaults = {o.get("Extension", "") for o in root if _localname(o.tag) == "Default"}
    found: list[str] = []
    for part in names - {"[Content_Types].xml"}:
        ext = part.rsplit(".", 1)[-1] if "." in part else ""
        if part not in overrides and ext not in defaults:
            found.append(f"[Content_Types].xml: no entry for {part}")
    return found
