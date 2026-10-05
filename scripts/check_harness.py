#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-docx", "Pillow", "lxml"]
# ///

# ─── How to run ───
# python3 check_harness.py

"""Deterministic checks for the report style CLI. No external report is required."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from check_specs import figure_spec, manuscript, ref_spec, valid_spec
from check_style import assert_geometry, assert_style, prefix_preserved
from docx import Document
from docx.shared import Cm
from PIL import Image

SKILL = Path(__file__).resolve().parent.parent
CLI = SKILL / "scripts" / "build_report.py"
TEMPLATE = SKILL / "template" / "report-style.docx"
ALLOW = {
    "word/document.xml",
    "word/_rels/document.xml.rels",
    "[Content_Types].xml",
    "docProps/app.xml",
    "docProps/core.xml",
}
SENTINEL = "ORIGINAL_BODY_SENTINEL_9f3a"


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the real CLI entry point."""
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def part(path: Path, name: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name)


def media_hashes(path: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("word/media/") or Path(name).name.startswith("thumbnail."):
                found[name] = hashlib.sha256(archive.read(name)).hexdigest()
    return found


def write_png(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    Image.new("RGB", size, color).save(path)


def build(directory: Path, source: Path, mode: str, *, extra: list[str] | None = None) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    wide = directory / "wide.png"
    tall = directory / "tall.png"
    write_png(wide, (2000, 500), (20, 40, 60))
    write_png(tall, (400, 2000), (60, 40, 20))
    spec = directory / "manuscript.json"
    spec.write_text(manuscript(wide, tall), encoding="utf-8")
    output = directory / f"{mode}.docx"
    before = sha256(source)
    args = ["--source", str(source), "--manuscript", str(spec), "--output", str(output), "--mode", mode]
    if extra:
        args.extend(extra)
    result = run_cli(args)
    assert result.returncode == 0, result.stderr
    assert sha256(source) == before
    audit = output.parent / f"{output.name}.audit.json"
    assert audit.is_file()
    return output, audit


def synthetic_source(directory: Path, images: list[tuple[str, tuple[int, int], tuple[int, int, int]]]) -> Path:
    dest = directory / "source.docx"
    shutil.copyfile(TEMPLATE, dest)
    document = Document(str(dest))
    document.add_paragraph(SENTINEL)
    for name, size, color in images:
        path = directory / name
        write_png(path, size, color)
        document.add_paragraph().add_run().add_picture(str(path), width=Cm(3))
    document.save(str(dest))
    return dest


def test_help_lists_modes() -> None:
    result = run_cli(["--help"])
    assert result.returncode == 0
    assert "--mode" in result.stdout
    assert "--source" in result.stdout
    assert "--manuscript" in result.stdout
    assert "--output" in result.stdout


def test_new_mode_preserves_style(tmp: Path) -> None:
    output, audit_path = build(tmp, TEMPLATE, "new")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["mode"] == "new"
    assert audit["body_policy"] == "replaced"
    assert audit["styles_unchanged"] is True
    assert audit["theme_unchanged"] is True
    assert audit["section_geometry_unchanged"] is True
    assert audit["leaked_source_text_count"] == 0
    assert audit["disallowed_package_parts"] == []
    assert part(output, "word/styles.xml") == part(TEMPLATE, "word/styles.xml")
    assert part(output, "word/theme/theme1.xml") == part(TEMPLATE, "word/theme/theme1.xml")
    blob = part(output, "word/document.xml")
    assert_geometry(blob)
    assert_style(blob)
    placed = {sha256(tmp / "wide.png"), sha256(tmp / "tall.png")}
    assert set(media_hashes(output).values()) == placed


def test_new_mode_drops_unrequested_and_keeps_requested(tmp: Path) -> None:
    source = synthetic_source(
        tmp,
        [("kept.png", (40, 20), (10, 20, 30)), ("dropped.png", (30, 30), (200, 10, 10))],
    )
    before = sha256(source)
    with zipfile.ZipFile(source) as archive:
        names = [name for name in archive.namelist() if name.startswith("word/media/")]
        kept_blob = archive.read(names[0])
        dropped = hashlib.sha256(archive.read(names[1])).hexdigest()
    reused = tmp / "reused.png"
    reused.write_bytes(kept_blob)
    kept = hashlib.sha256(kept_blob).hexdigest()
    spec = tmp / "reuse.json"
    spec.write_text(
        json.dumps(
            {
                "blocks": [
                    {"type": "p", "text": "See Figure K."},
                    {
                        "type": "figure",
                        "id": "K",
                        "mention": "Figure K",
                        "asset": "kept",
                        "source": "kept-source-token",
                        "caption": "Figure K. kept-source-token.",
                    },
                ],
                "assets": {"kept": {"path": str(reused)}},
            }
        ),
        encoding="utf-8",
    )
    output = tmp / "new.docx"
    result = run_cli(
        ["--source", str(source), "--manuscript", str(spec), "--output", str(output), "--mode", "new"]
    )
    assert result.returncode == 0, result.stderr
    blob = part(output, "word/document.xml")
    assert SENTINEL.encode() not in blob
    hashes = set(media_hashes(output).values())
    assert kept in hashes
    assert dropped not in hashes
    assert sha256(source) == before


def test_append_preserves_package(tmp: Path) -> None:
    source = synthetic_source(tmp, [("original.png", (24, 24), (1, 2, 3))])
    before_parts = media_hashes(source)
    output, audit_path = build(tmp / "append-run", source, "append")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["mode"] == "append"
    assert audit["original_body_xml_prefix_preserved"] is True
    assert audit["original_media_retained"] is True
    assert audit["styles_unchanged"] is True
    assert audit["removed_parts"] == []
    assert set(audit["changed_parts"]) <= ALLOW
    assert audit["disallowed_package_parts"] == []
    assert all(name.startswith("word/media/") for name in audit["added_parts"])
    assert prefix_preserved(part(source, "word/document.xml"), part(output, "word/document.xml"))
    assert SENTINEL.encode() in part(output, "word/document.xml")
    after_parts = media_hashes(output)
    for name, digest in before_parts.items():
        assert after_parts[name] == digest


def test_default_source_without_figures(tmp: Path) -> None:
    spec = tmp / "note.json"
    spec.write_text(
        json.dumps({"blocks": [{"type": "h", "level": 1, "text": "NOTE"}, {"type": "p", "text": "No figure and no citation."}]}),
        encoding="utf-8",
    )
    output = tmp / "note.docx"
    before = sha256(TEMPLATE)
    result = run_cli(["--manuscript", str(spec), "--output", str(output), "--mode", "new"])
    assert result.returncode == 0, result.stderr
    assert sha256(TEMPLATE) == before
    assert part(output, "word/styles.xml") == part(TEMPLATE, "word/styles.xml")
    assert b"NOTE" in part(output, "word/document.xml")


def test_reject_malformed_missing_and_overwrite(tmp: Path) -> None:
    tiny = tmp / "tiny.docx"
    write_png(tmp / "ok.png", (8, 8), (1, 2, 3))
    Document().save(str(tiny))
    before = sha256(tiny)
    png_before = sha256(tmp / "ok.png")
    bad = tmp / "bad.json"
    bad.write_text("{", encoding="utf-8")
    malformed = run_cli(["--source", str(tiny), "--manuscript", str(bad), "--output", str(tmp / "out.docx"), "--mode", "new"])
    missing_figure = _reject(tmp, tiny, figure_spec(tmp, asset=str(tmp / "absent.png"), previous="Figure F is here.", caption="Figure F. source-token."))
    missing_mention = _reject(tmp, tiny, figure_spec(tmp, asset=str(tmp / "ok.png"), previous="No token here.", caption="Figure F. source-token."))
    missing_source = _reject(tmp, tiny, figure_spec(tmp, asset=str(tmp / "ok.png"), previous="Figure F is here.", caption="Figure F without provenance."))
    missing_ref = _reject(tmp, tiny, ref_spec(tmp, cite=False))
    unknown_ref = _reject(tmp, tiny, ref_spec(tmp, cite=True, extra="[MISSING]"))
    existing = tmp / "exists.docx"
    existing.write_bytes(b"keep")
    valid = valid_spec(tmp)
    overwrite = run_cli(["--source", str(tiny), "--manuscript", str(valid), "--output", str(existing), "--mode", "new"])
    collision = run_cli(["--source", str(tiny), "--manuscript", str(valid), "--output", str(tiny), "--mode", "append"])
    asset_hit = run_cli(["--source", str(tiny), "--manuscript", str(valid), "--output", str(tmp / "ok.png"), "--mode", "new"])
    assert malformed.returncode == 2 and "malformed_manuscript" in malformed.stderr
    assert "missing_figure" in missing_figure
    assert "missing_figure_mention" in missing_mention
    assert "missing_figure_source" in missing_source
    assert "missing_reference" in missing_ref
    assert "missing_reference" in unknown_ref
    assert overwrite.returncode == 2 and "output_exists" in overwrite.stderr
    assert existing.read_bytes() == b"keep"
    assert collision.returncode == 2 and "output_collides" in collision.stderr
    assert asset_hit.returncode == 2 and "output_collides" in asset_hit.stderr
    assert sha256(tiny) == before
    assert sha256(tmp / "ok.png") == png_before


def test_append_without_source_errors(tmp: Path) -> None:
    spec = tmp / "note.json"
    spec.write_text('{"blocks":[{"type":"p","text":"Note."}]}', encoding="utf-8")
    output = tmp / "out.docx"
    result = run_cli(["--manuscript", str(spec), "--output", str(output), "--mode", "append"])
    assert result.returncode == 2 and "missing_source" in result.stderr
    assert not output.exists()


def test_windows_path_is_preserved(tmp: Path) -> None:
    """Literal prose paths survive the actual CLI and Word text round trip."""
    # Given: ordinary technical prose, not an equation.
    text = r"The input is C:\data\input.csv."
    spec = tmp / "path.json"
    spec.write_text(json.dumps({"blocks": [{"type": "p", "text": text}]}), encoding="utf-8")
    output = tmp / "path.docx"
    # When: the real CLI builds it.
    result = run_cli(["--manuscript", str(spec), "--output", str(output), "--mode", "new"])
    # Then: the machine-consumed manuscript value is preserved, not rewritten.
    assert result.returncode == 0, result.stderr
    assert Document(str(output)).paragraphs[0].text == text


def test_indexing_is_not_citation(tmp: Path) -> None:
    """Identifiers and chained indexing need no fabricated bibliography."""
    # Given: literal indexing without reference entries.
    text = "Read samples[0] and matrix[row][col] as indexed values."
    spec = tmp / "index.json"
    spec.write_text(json.dumps({"blocks": [{"type": "p", "text": text}]}), encoding="utf-8")
    output = tmp / "index.docx"
    # When: the real CLI builds it.
    result = run_cli(["--manuscript", str(spec), "--output", str(output), "--mode", "new"])
    # Then: the original literal expression survives.
    assert result.returncode == 0, result.stderr
    assert Document(str(output)).paragraphs[0].text == text


def test_latex_equation_is_rejected(tmp: Path) -> None:
    """Equation blocks still reject unsupported LaTeX commands."""
    # Given: unsupported equation syntax.
    spec = tmp / "latex.json"
    spec.write_text(json.dumps({"blocks": [{"type": "eq", "lines": [r"\frac{1}{2}"]}]}), encoding="utf-8")
    output = tmp / "latex.docx"
    # When: the real CLI attempts the build.
    result = run_cli(["--manuscript", str(spec), "--output", str(output), "--mode", "new"])
    # Then: no misleading editable-linear-equation output is emitted.
    assert result.returncode == 2 and "latex_marker" in result.stderr
    assert not output.exists()


def test_author_year_does_not_require_bracket_keys(tmp: Path) -> None:
    """Author-year references do not need a fabricated [key] citation."""
    # Given: an in-text author-year fragment and no bracket key.
    text = "The note states the relation (Ada Lovelace, 1843)."
    spec = tmp / "author-year.json"
    spec.write_text(
        json.dumps(
            {
                "citation_style": "author-year",
                "blocks": [{"type": "p", "text": text}],
                "references": [
                    {
                        "key": "Lovelace1843",
                        "cite": "Ada Lovelace, 1843",
                        "text": "Lovelace, A. (1843). A note on an analytical engine. Example Journal, 1, 1-2.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp / "author-year.docx"
    # When: the real CLI builds it.
    result = run_cli(["--manuscript", str(spec), "--output", str(output), "--mode", "new"])
    # Then: the author-year sentence is preserved and no bracket key was required.
    assert result.returncode == 0, result.stderr
    assert Document(str(output)).paragraphs[0].text == text
    assert b"[Lovelace1843]" not in part(output, "word/document.xml")


def test_author_year_missing_citation_is_rejected(tmp: Path) -> None:
    """An author-year entry that never appears in a paragraph is rejected."""
    # Given: a reference whose cite fragment is absent from the body.
    spec = tmp / "author-year-missing.json"
    spec.write_text(
        json.dumps(
            {
                "blocks": [{"type": "p", "text": "No in-text citation appears here."}],
                "references": [
                    {
                        "key": "Lovelace1843",
                        "cite": "Ada Lovelace, 1843",
                        "text": "Lovelace, A. (1843). A note on an analytical engine.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp / "author-year-missing.docx"
    # When: the real CLI attempts the build.
    result = run_cli(["--manuscript", str(spec), "--output", str(output), "--mode", "new"])
    # Then: the missing citation is rejected and no file is written.
    assert result.returncode == 2 and "missing_reference" in result.stderr
    assert not output.exists()


def test_numbered_style_still_requires_keys(tmp: Path) -> None:
    """Explicit numbered style does not accept an author-year sentence as a citation."""
    # Given: a numbered request whose body has no [key].
    spec = tmp / "numbered.json"
    spec.write_text(
        json.dumps(
            {
                "citation_style": "numbered",
                "blocks": [{"type": "p", "text": "Only an author-year mention (Ada Lovelace, 1843)."}],
                "references": [{"key": "L1", "text": "[L1] Lovelace note."}],
            }
        ),
        encoding="utf-8",
    )
    output = tmp / "numbered.docx"
    # When: the real CLI attempts the build.
    result = run_cli(["--manuscript", str(spec), "--output", str(output), "--mode", "new"])
    # Then: the numbered contract still fails closed.
    assert result.returncode == 2 and "missing_reference" in result.stderr
    assert not output.exists()


def test_callouts_use_source_block_style(tmp: Path) -> None:
    """Learning and summary callouts preserve the source's actual visual style."""
    # Given: two native callout paragraphs in the textbook template.
    spec = tmp / "callout.json"
    spec.write_text(json.dumps({"blocks": [
        {"type": "p", "role": "callout-title", "text": "LEARNING_TITLE"},
        {"type": "p", "role": "callout-body", "text": "LEARNING_BODY"},
    ]}), encoding="utf-8")
    output = tmp / "callout.docx"
    # When: the real CLI builds the manuscript.
    result = run_cli(["--manuscript", str(spec), "--output", str(output), "--mode", "new"])
    # Then: both paragraphs use the source callout style, not unstyled prose.
    assert result.returncode == 0, result.stderr
    paragraphs = Document(str(output)).paragraphs
    assert [p.style.style_id for p in paragraphs] == ["BlockText", "BlockText"]
    assert paragraphs[0].runs[0].bold is True
    assert paragraphs[0].paragraph_format.keep_with_next is True
    assert part(output, "word/styles.xml") == part(TEMPLATE, "word/styles.xml")


def _reject(tmp: Path, source: Path, spec: Path) -> str:
    result = run_cli(
        ["--source", str(source), "--manuscript", str(spec), "--output", str(tmp / f"{spec.stem}.docx"), "--mode", "new"]
    )
    assert result.returncode == 2
    return result.stderr


def main() -> None:
    """Run every check in its own directory."""
    if not TEMPLATE.is_file():
        raise SystemExit(f"missing template: {TEMPLATE}")
    test_help_lists_modes()
    print("PASS help")
    named = (
        ("new", test_new_mode_preserves_style),
        ("reuse", test_new_mode_drops_unrequested_and_keeps_requested),
        ("append", test_append_preserves_package),
        ("plain", test_default_source_without_figures),
        ("reject", test_reject_malformed_missing_and_overwrite),
        ("append-source", test_append_without_source_errors),
        ("windows-path", test_windows_path_is_preserved),
        ("literal-index", test_indexing_is_not_citation),
        ("latex-equation", test_latex_equation_is_rejected),
        ("author-year", test_author_year_does_not_require_bracket_keys),
        ("author-year-missing", test_author_year_missing_citation_is_rejected),
        ("numbered-style", test_numbered_style_still_requires_keys),
        ("callout-style", test_callouts_use_source_block_style),
    )
    for name, test in named:
        with tempfile.TemporaryDirectory(prefix=f"report-style-{name}-") as tmp:
            test(Path(tmp))
        print(f"PASS {name}")


if __name__ == "__main__":
    main()
