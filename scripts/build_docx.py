"""Build a new or appended DOCX without modifying the style source."""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import assert_never

from docx import Document
from docx.document import Document as DocumentType
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.ns import qn

from audit_model import BuildAudit, BuildMode, make_audit
from errors import CollisionError, HarnessError, PackageError
from manuscript import (
    EquationBlock,
    FigureBlock,
    HeadingBlock,
    LoadedManuscript,
    ParagraphBlock,
    TableBlock,
    load_manuscript,
    rendered_strings,
)
from package_audit import (
    disallowed_package_changes,
    document_xml,
    embedded_hashes,
    geometry_token,
    leaked_source_texts,
    media_parts_preserved,
    part_hashes,
    prefix_preserved,
)
from render import render
from zip_package import prune_new_package, restore_style_parts, sha256_file


def parse_mode(value: str) -> BuildMode:
    """Parse the CLI mode string."""
    try:
        return BuildMode(value)
    except ValueError:
        raise PackageError("malformed_mode", value) from None


def build_report(
    source: Path,
    manuscript_path: Path,
    output: Path,
    mode: BuildMode,
    audit_path: Path | None = None,
) -> BuildAudit:
    """Create output from source styles and a manuscript. Never writes to source."""
    if not source.is_file():
        raise PackageError("missing_source", str(source))
    loaded = load_manuscript(manuscript_path)
    audit_dest = audit_path if audit_path is not None else output.parent / f"{output.name}.audit.json"
    assert_safe_outputs(output, audit_dest, [source, manuscript_path, *loaded.assets.values()])
    source_hash = sha256_file(source)
    with tempfile.TemporaryDirectory(prefix="report-style-") as tmp:
        staged = Path(tmp) / "staged.docx"
        if staged.resolve() == source.resolve():
            raise CollisionError("output_collides", str(staged))
        shutil.copyfile(source, staged)
        add_break = False
        match mode:
            case BuildMode.NEW:
                clear_body(staged)
                prune_new_package(staged)
                body_policy = "replaced"
            case BuildMode.APPEND:
                body_policy = "appended"
                add_break = True
            case unreachable:
                assert_never(unreachable)
        document = open_document(staged)
        if add_break:
            document.add_page_break()
        render(document, loaded)
        document.save(str(staged))
        restored = restore_style_parts(source, staged)
        _reject_broken(source, staged, loaded, mode)
        if sha256_file(source) != source_hash:
            raise PackageError("source_changed", str(source))
        payload = staged.read_bytes()
    ensure_parent(output)
    ensure_parent(audit_dest)
    exclusive_write(output, payload)
    output_hash = sha256_file(output)
    audit = make_audit(
        mode=mode,
        body_policy=body_policy,
        source=source,
        manuscript_path=manuscript_path,
        output=output,
        source_hash=source_hash,
        output_hash=output_hash,
        restored=restored,
        loaded=loaded,
    )
    try:
        exclusive_write(audit_dest, audit.model_dump_json(indent=2).encode("utf-8") + b"\n")
    except HarnessError:
        output.unlink(missing_ok=True)
        raise
    if sha256_file(source) != source_hash:
        output.unlink(missing_ok=True)
        audit_dest.unlink(missing_ok=True)
        raise PackageError("source_changed", str(source))
    return audit


def assert_safe_outputs(output: Path, audit: Path, protected: list[Path]) -> None:
    """Reject overwrite and any output path that is an input or asset."""
    if output.resolve() == audit.resolve():
        raise CollisionError("output_collides", "audit path equals output")
    protected_resolved = {item.resolve() for item in protected if item.exists()}
    for path in (output, audit):
        if path.resolve() in protected_resolved:
            raise CollisionError("output_collides", str(path))
        if path.exists() or path.is_symlink():
            raise CollisionError("output_exists", str(path))


def clear_body(path: Path) -> None:
    """Remove body content and keep the final section properties."""
    document = open_document(path)
    body = document.element.body
    sect = body.find(qn("w:sectPr"))
    if sect is None:
        raise PackageError("missing_section", path.name)
    for child in list(body):
        if child is not sect:
            body.remove(child)
    document.save(str(path))


def open_document(path: Path) -> DocumentType:
    """Open a DOCX or raise a package error."""
    try:
        document: DocumentType = Document(str(path))
    except (zipfile.BadZipFile, PackageNotFoundError, KeyError) as exc:
        raise PackageError("package_unreadable", type(exc).__name__) from None
    return document


def exclusive_write(path: Path, payload: bytes) -> None:
    """Create a file only when it does not already exist."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        descriptor = os.open(path, flags, 0o644)
    except FileExistsError:
        raise CollisionError("output_exists", str(path)) from None
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)


def ensure_parent(path: Path) -> None:
    """Create the output directory. A file in the way is an error."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise PackageError("output_unwritable", str(path.parent)) from None


def _reject_broken(source: Path, staged: Path, loaded: LoadedManuscript, mode: BuildMode) -> None:
    source_xml = document_xml(source)
    output_xml = document_xml(staged)
    if geometry_token(source_xml) != geometry_token(output_xml):
        raise PackageError("section_geometry_changed", source.name)
    old = part_hashes(source)
    new = part_hashes(staged)
    if old.get("word/styles.xml") != new.get("word/styles.xml"):
        raise PackageError("style_not_preserved", "word/styles.xml")
    if old.get("word/theme/theme1.xml") != new.get("word/theme/theme1.xml"):
        raise PackageError("style_not_preserved", "word/theme/theme1.xml")
    requested = _placed_hashes(loaded)
    output_embedded = embedded_hashes(staged)
    if requested - output_embedded:
        raise PackageError("missing_figure", "requested image was not embedded")
    leaks = leaked_source_texts(source_xml, staged, rendered_strings(loaded.manuscript))
    match mode:
        case BuildMode.NEW:
            unintended = (embedded_hashes(source) & output_embedded) - requested
            if unintended:
                raise PackageError("media_leaked", source.name)
            if leaks:
                raise PackageError("text_leaked", str(len(leaks)))
        case BuildMode.APPEND:
            if not prefix_preserved(source_xml, output_xml):
                raise PackageError("body_not_preserved", source.name)
            if not media_parts_preserved(source, staged):
                raise PackageError("media_not_preserved", source.name)
            disallowed = disallowed_package_changes(source, staged)
            if disallowed:
                joined = ", ".join(disallowed[:8])
                raise PackageError("package_part_changed", joined)
        case unreachable:
            assert_never(unreachable)


def _placed_hashes(loaded: LoadedManuscript) -> set[str]:
    """Hashes of figure files the manuscript explicitly places."""
    found: set[str] = set()
    for block in loaded.manuscript.blocks:
        match block:
            case FigureBlock(asset=asset):
                found.add(sha256_file(loaded.assets[asset]))
            case HeadingBlock() | ParagraphBlock() | EquationBlock() | TableBlock():
                pass
            case unreachable:
                assert_never(unreachable)
    return found
