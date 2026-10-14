"""ZIP-level style reuse, media pruning, and package audit measurements."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path
from typing import Final

try:
    # lxml preserves original namespace prefixes and declarations referenced
    # only inside attribute values (xsi:type, mc:Ignorable); stdlib ElementTree
    # rewrites prefixes to ns0/ns1 and drops those declarations, producing
    # packages Word rejects as unreadable.
    from lxml import etree as ET
    _HAS_LXML = True
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as ET
    _HAS_LXML = False

from errors import PackageError

W_NS: Final = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W: Final = f"{{{W_NS}}}"
REL_NS: Final = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS: Final = "http://schemas.openxmlformats.org/package/2006/content-types"
MIN_LEAK_CHARS: Final = 12
APPEND_MUTABLE_PARTS: Final[tuple[str, ...]] = (
    "word/document.xml",
    "word/_rels/document.xml.rels",
    "[Content_Types].xml",
    "docProps/app.xml",
    "docProps/core.xml",
)
STYLE_PARTS: Final[tuple[str, ...]] = (
    "word/styles.xml",
    "word/stylesWithEffects.xml",
    "word/theme/theme1.xml",
    "word/fontTable.xml",
    "word/numbering.xml",
)
KEEP_EXACT: Final[frozenset[str]] = frozenset(
    {
        "[Content_Types].xml",
        "_rels/.rels",
        "docProps/core.xml",
        "docProps/app.xml",
        "word/document.xml",
        "word/_rels/document.xml.rels",
        "word/styles.xml",
        "word/stylesWithEffects.xml",
        "word/settings.xml",
        "word/webSettings.xml",
        "word/fontTable.xml",
        "word/theme/theme1.xml",
        "word/numbering.xml",
    }
)
TEXT_PARTS: Final[frozenset[str]] = frozenset(
    {"word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"}
)
CORE_FIELDS: Final[frozenset[str]] = frozenset({"title", "subject", "description", "keywords"})
DRAWING_NAMES: Final[frozenset[str]] = frozenset({"drawing", "pict", "object"})


def sha256_file(path: Path) -> str:
    """Hash a file without loading it all at once."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(blob: bytes) -> str:
    """Hash one ZIP part."""
    return hashlib.sha256(blob).hexdigest()


def part_map(path: Path) -> dict[str, bytes]:
    """Read every package part. Internal scratch map, not a public contract."""
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def part_hashes(path: Path) -> dict[str, str]:
    """Hash every package part."""
    return {name: sha256_bytes(blob) for name, blob in part_map(path).items()}


def write_parts(path: Path, parts: dict[str, bytes]) -> None:
    """Replace a package with the given part bytes."""
    buffer = io.BytesIO()
    names = sorted(name for name in parts if name != "[Content_Types].xml")
    if "[Content_Types].xml" in parts:
        names.insert(0, "[Content_Types].xml")
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.writestr(name, parts[name])
    path.write_bytes(buffer.getvalue())


def prune_new_package(path: Path) -> None:
    """Drop old media and non-style parts. Keep styles, theme, and sectPr."""
    original = part_map(path)
    kept = {name for name in original if keep_part(name)}
    parts = {name: original[name] for name in kept}
    for name in list(parts):
        if is_text_carrier(name):
            parts[name] = strip_text_and_drawings(parts[name])
        if name == "docProps/core.xml":
            parts[name] = blank_core_fields(parts[name])
        if name.endswith(".rels"):
            parts[name] = prune_relationships(parts[name], name, kept)
        if name == "[Content_Types].xml":
            parts[name] = prune_content_types(parts[name], kept)
    write_parts(path, parts)


def restore_style_parts(source: Path, dest: Path) -> list[str]:
    """Copy style and theme parts from the untouched source when a save rewrote them."""
    source_parts = part_map(source)
    dest_parts = part_map(dest)
    restored: list[str] = []
    for name in STYLE_PARTS:
        if name not in source_parts:
            continue
        if dest_parts.get(name) == source_parts[name]:
            continue
        dest_parts[name] = source_parts[name]
        restored.append(name)
    if restored:
        write_parts(dest, dest_parts)
    return restored


def keep_part(name: str) -> bool:
    """Style, geometry, and blanked header/footnote carriers stay. Media does not."""
    if name.startswith(("word/media/", "word/embeddings/", "customXml/", "docProps/thumbnail")):
        return False
    if name in KEEP_EXACT or name in TEXT_PARTS:
        return True
    if name.startswith(("word/header", "word/footer")):
        return True
    owner = rels_owner(name)
    return owner is not None and keep_part(owner)


def rels_owner(name: str) -> str | None:
    """Map word/_rels/header1.xml.rels to word/header1.xml."""
    if not name.startswith("word/_rels/") or not name.endswith(".rels"):
        return None
    return f"word/{Path(name).name.removesuffix('.rels')}"


def is_text_carrier(name: str) -> bool:
    """Header, footer, note, and comment parts can carry old report text."""
    return name in TEXT_PARTS or name.startswith(("word/header", "word/footer"))


def prune_relationships(xml: bytes, rels_name: str, kept: set[str]) -> bytes:
    """Drop relationships whose targets were removed."""
    root = ET.fromstring(xml)
    for rel in list(root):
        if not _keep_relationship(rel, rels_name, kept):
            root.remove(rel)
    return _xml_bytes(root)


def prune_content_types(xml: bytes, kept: set[str]) -> bytes:
    """Drop overrides for parts that are no longer in the package."""
    root = ET.fromstring(xml)
    for child in list(root):
        if _local(child) != "Override":
            continue
        part = (child.get("PartName") or "").lstrip("/")
        if part not in kept:
            root.remove(child)
    return _xml_bytes(root)


def blank_core_fields(xml: bytes) -> bytes:
    """Remove descriptive core properties that can carry the old title."""
    root = ET.fromstring(xml)
    for el in root.iter():
        if _local(el) in CORE_FIELDS and el.text:
            el.text = ""
    return _xml_bytes(root)


def strip_text_and_drawings(xml: bytes) -> bytes:
    """Empty a header, footer, or note part without removing the part."""
    root = ET.fromstring(xml)
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    for el in [item for item in root.iter() if _local(item) in DRAWING_NAMES]:
        owner = parents.get(el)
        if owner is not None:
            owner.remove(el)
    for el in root.iter():
        if _local(el) == "t" and el.text:
            el.text = ""
    return _xml_bytes(root)


def _keep_relationship(rel: ET.Element, rels_name: str, kept: set[str]) -> bool:
    if rel.get("TargetMode") == "External":
        return True
    target = rel.get("Target")
    if target is None:
        return False
    return _resolve_target(rels_name, target) in kept


def _resolve_target(rels_name: str, target: str) -> str:
    return (Path(rels_name).parent.parent / target).as_posix()


def _local(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _xml_bytes(root: ET.Element) -> bytes:
    if not _HAS_LXML:
        raise PackageError(
            "lxml_required",
            "package reserialization needs lxml; stdlib ElementTree corrupts namespaces",
        )
    return ET.tostring(root, xml_declaration=True, encoding="UTF-8")
