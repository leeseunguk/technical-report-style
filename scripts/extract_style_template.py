#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-docx", "lxml"]
# ///

# ─── How to run ───
# python3 extract_style_template.py --source STYLE_SOURCE.docx --output template/report-style.docx

"""Write a clean style-only DOCX from an existing document. Does not modify the source."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from build_docx import clear_body, exclusive_write, open_document
from errors import CollisionError, HarnessError, PackageError
from package_audit import document_xml, embedded_hashes, geometry_token, leaked_source_texts
from zip_package import part_hashes, prune_new_package, restore_style_parts, sha256_file

app = typer.Typer(add_completion=False, no_args_is_help=True)


def default_output() -> Path:
    """Bundled template path next to the scripts directory."""
    return Path(__file__).resolve().parent.parent / "template" / "report-style.docx"


@app.command()
def main(
    source: Annotated[Path, typer.Option("--source", help="Document whose styles and section geometry are copied.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Style-only DOCX to create. Refuses overwrite."),
    ] = None,
) -> None:
    """Extract styles, theme, and section geometry. Drop body text and media."""
    dest = default_output() if output is None else output
    try:
        extract_style_template(source, dest)
    except HarnessError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from None
    typer.echo(f"TEMPLATE {dest}")


def extract_style_template(source: Path, output: Path) -> None:
    """Create a style-only package. The source file is only read."""
    if not source.is_file():
        raise PackageError("missing_source", str(source))
    if output.exists() or output.is_symlink():
        raise CollisionError("output_exists", str(output))
    if output.resolve() == source.resolve():
        raise CollisionError("output_collides", str(output))
    before = sha256_file(source)
    with tempfile.TemporaryDirectory(prefix="report-style-") as tmp:
        staged = Path(tmp) / "template.docx"
        shutil.copyfile(source, staged)
        clear_body(staged)
        prune_new_package(staged)
        restore_style_parts(source, staged)
        open_document(staged)
        _reject_dirty_template(source, staged)
        if sha256_file(source) != before:
            raise PackageError("source_changed", str(source))
        payload = staged.read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    exclusive_write(output, payload)


def _reject_dirty_template(source: Path, staged: Path) -> None:
    old = part_hashes(source)
    new = part_hashes(staged)
    if old.get("word/styles.xml") != new.get("word/styles.xml"):
        raise PackageError("style_not_preserved", "word/styles.xml")
    if old.get("word/theme/theme1.xml") != new.get("word/theme/theme1.xml"):
        raise PackageError("style_not_preserved", "word/theme/theme1.xml")
    source_xml = document_xml(source)
    output_xml = document_xml(staged)
    if geometry_token(source_xml) != geometry_token(output_xml):
        raise PackageError("section_geometry_changed", source.name)
    if embedded_hashes(staged):
        raise PackageError("media_leaked", source.name)
    leaks = leaked_source_texts(source_xml, staged, [])
    if leaks:
        raise PackageError("text_leaked", str(len(leaks)))


if __name__ == "__main__":
    app()
