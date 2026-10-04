"""Audit record for a successful DOCX build."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import assert_never

from pydantic import BaseModel, ConfigDict

from manuscript import LoadedManuscript, figure_count, rendered_strings
from package_audit import (
    disallowed_package_changes,
    document_xml,
    geometry_token,
    leaked_source_texts,
    media_parts_preserved,
    part_delta,
    part_hashes,
    prefix_preserved,
)
from zip_package import APPEND_MUTABLE_PARTS, sha256_file


class BuildMode(StrEnum):
    """CLI mode. There is no overwrite flag."""

    NEW = "new"
    APPEND = "append"


class BuildAudit(BaseModel):
    """Machine audit written beside a successful deliverable."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    mode: BuildMode
    body_policy: str
    source: str
    manuscript: str
    output: str
    source_sha256: str
    source_unchanged: bool
    output_sha256: str
    styles_unchanged: bool
    theme_unchanged: bool
    section_geometry_unchanged: bool
    source_section_geometry: str
    output_section_geometry: str
    original_body_xml_prefix_preserved: bool
    original_media_retained: bool
    leaked_source_text_count: int
    changed_parts: list[str]
    added_parts: list[str]
    removed_parts: list[str]
    style_parts_restored: list[str]
    allowed_changed_parts: list[str]
    disallowed_package_parts: list[str]
    figure_count: int
    reference_count: int


def make_audit(
    *,
    mode: BuildMode,
    body_policy: str,
    source: Path,
    manuscript_path: Path,
    output: Path,
    source_hash: str,
    output_hash: str,
    restored: list[str],
    loaded: LoadedManuscript,
) -> BuildAudit:
    """Record what the build preserved and which package parts changed."""
    source_xml = document_xml(source)
    output_xml = document_xml(output)
    changed, added, removed = part_delta(source, output)
    leaks = leaked_source_texts(source_xml, output, rendered_strings(loaded.manuscript))
    match mode:
        case BuildMode.APPEND:
            allowed = list(APPEND_MUTABLE_PARTS)
            disallowed = disallowed_package_changes(source, output)
        case BuildMode.NEW:
            allowed = []
            disallowed = []
        case unreachable:
            assert_never(unreachable)
    styles = part_hashes(source)
    output_styles = part_hashes(output)
    return BuildAudit(
        mode=mode,
        body_policy=body_policy,
        source=str(source),
        manuscript=str(manuscript_path),
        output=str(output),
        source_sha256=source_hash,
        source_unchanged=sha256_file(source) == source_hash,
        output_sha256=output_hash,
        styles_unchanged=styles.get("word/styles.xml") == output_styles.get("word/styles.xml"),
        theme_unchanged=styles.get("word/theme/theme1.xml") == output_styles.get("word/theme/theme1.xml"),
        section_geometry_unchanged=geometry_token(source_xml) == geometry_token(output_xml),
        source_section_geometry=geometry_token(source_xml),
        output_section_geometry=geometry_token(output_xml),
        original_body_xml_prefix_preserved=prefix_preserved(source_xml, output_xml),
        original_media_retained=media_parts_preserved(source, output),
        leaked_source_text_count=len(leaks),
        changed_parts=changed,
        added_parts=added,
        removed_parts=removed,
        style_parts_restored=restored,
        allowed_changed_parts=allowed,
        disallowed_package_parts=disallowed,
        figure_count=figure_count(loaded.manuscript),
        reference_count=len(loaded.manuscript.references),
    )
