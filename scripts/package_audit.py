"""Compare DOCX packages after a build. Pruning stays in zip_package."""

from __future__ import annotations

from pathlib import Path

import xml.etree.ElementTree as ET

from errors import PackageError
from zip_package import (
    APPEND_MUTABLE_PARTS,
    MIN_LEAK_CHARS,
    W,
    part_hashes,
    part_map,
    sha256_bytes,
)


def document_xml(path: Path) -> bytes:
    """Return word/document.xml."""
    try:
        return part_map(path)["word/document.xml"]
    except KeyError:
        raise PackageError("package_unreadable", "word/document.xml") from None


def prefix_preserved(source_xml: bytes, output_xml: bytes) -> bool:
    """True when every original body child is an unchanged prefix of the output."""
    old = _body_children(source_xml)
    new = _body_children(output_xml)
    return len(new) >= len(old) and new[: len(old)] == old


def geometry_token(blob: bytes) -> str:
    """Stable section-geometry token from the final sectPr."""
    kids = list(_body(blob))
    if not kids or _local(kids[-1]) != "sectPr":
        raise PackageError("missing_section", "sectPr")
    parts: list[str] = []
    for child in kids[-1]:
        attrs = ",".join(
            f"{_attr_name(key)}={value}"
            for key, value in sorted(child.attrib.items(), key=lambda item: _attr_name(item[0]))
        )
        parts.append(f"{_local(child)}[{attrs}]")
    return "|".join(parts)


def embedded_hashes(path: Path) -> set[str]:
    """Hashes of media and thumbnail parts."""
    return {sha256_bytes(blob) for name, blob in part_map(path).items() if _is_embedded(name)}


def media_parts_preserved(source: Path, output: Path) -> bool:
    """True when every source media and thumbnail part is byte-identical."""
    old = part_hashes(source)
    new = part_hashes(output)
    return all(new.get(name) == digest for name, digest in old.items() if _is_embedded(name))


def disallowed_package_changes(source: Path, output: Path) -> list[str]:
    """Parts outside the append save allowlist, including removals and unexpected adds."""
    old = part_hashes(source)
    new = part_hashes(output)
    allowed = set(APPEND_MUTABLE_PARTS)
    bad = [name for name, digest in old.items() if name not in new or (digest != new[name] and name not in allowed)]
    bad.extend(name for name in new if name not in old and not name.startswith("word/media/"))
    return sorted(bad)


def leaked_source_texts(source_xml: bytes, output: Path, allowed: list[str]) -> list[str]:
    """Source body strings of meaningful length that survived outside the manuscript."""
    allowed_blob = "\n".join(allowed)
    needles = [text for text in _text_nodes(source_xml) if len(text) >= MIN_LEAK_CHARS and text not in allowed_blob]
    if not needles:
        return []
    haystack = "\n".join(_xml_texts(output))
    return [text for text in needles if text in haystack]


def part_delta(source: Path, output: Path) -> tuple[list[str], list[str], list[str]]:
    """Changed, added, and removed part names."""
    old = part_hashes(source)
    new = part_hashes(output)
    changed = sorted(name for name in old if name in new and old[name] != new[name])
    added = sorted(name for name in new if name not in old)
    removed = sorted(name for name in old if name not in new)
    return changed, added, removed


def _is_embedded(name: str) -> bool:
    return name.startswith("word/media/") or Path(name).name.startswith("thumbnail.")


def _body(blob: bytes) -> ET.Element:
    root = ET.fromstring(blob)
    body = root.find(f"{W}body")
    if body is None:
        raise PackageError("missing_section", "body")
    return body


def _body_children(blob: bytes) -> list[bytes]:
    kids = list(_body(blob))
    if kids and _local(kids[-1]) == "sectPr":
        kids = kids[:-1]
    return [ET.tostring(kid) for kid in kids]


def _text_nodes(blob: bytes) -> list[str]:
    root = ET.fromstring(blob)
    return [el.text for el in root.iter(f"{W}t") if el.text]


def _local(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _attr_name(key: str) -> str:
    return key.rsplit("}", 1)[-1]


def _xml_texts(path: Path) -> list[str]:
    return [
        blob.decode("utf-8", "replace")
        for name, blob in part_map(path).items()
        if name.endswith(".xml") or name.endswith(".rels")
    ]
