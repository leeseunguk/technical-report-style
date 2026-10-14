#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-docx", "Pillow", "pydantic>=2", "typer", "lxml", "latex2mathml", "mathml2omml"]
# ///

# ─── How to run ───
# python3 build_report.py --help
# python3 build_report.py --manuscript manuscript.json --output OUT.docx --mode new

"""Build a DOCX that reuses a source document's styles."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, assert_never

import typer

from audit_model import BuildMode
from build_docx import build_report, parse_mode
from errors import HarnessError, PackageError

app = typer.Typer(add_completion=False, no_args_is_help=True)


def bundled_template() -> Path:
    """Style-only template shipped beside this script. No external report is required."""
    return Path(__file__).resolve().parent.parent / "template" / "report-style.docx"


@app.command()
def main(
    manuscript: Annotated[Path, typer.Option("--manuscript", help="JSON manuscript.")],
    output: Annotated[Path, typer.Option("--output", help="New DOCX path. Overwrite is rejected.")],
    mode: Annotated[str, typer.Option("--mode", help="new or append.")],
    source: Annotated[
        Path | None,
        typer.Option("--source", help="Style source DOCX. Required for append. Defaults to the bundled template for new."),
    ] = None,
    audit: Annotated[
        Path | None,
        typer.Option("--audit", help="Audit JSON path. Default: <output>.audit.json"),
    ] = None,
    ledger: Annotated[
        Path | None,
        typer.Option("--ledger", help="Source ledger JSON. Checked only; never written into the DOCX."),
    ] = None,
) -> None:
    """Reuse styles. new drops old body and unrequested media; append keeps them."""
    try:
        parsed = parse_mode(mode)
        chosen = _source_for(parsed, source)
        build_report(chosen, manuscript, output, parsed, audit, ledger_path=ledger)
    except HarnessError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from None
    audit_path = audit if audit is not None else output.parent / f"{output.name}.audit.json"
    typer.echo(f"WROTE {output}")
    typer.echo(f"AUDIT {audit_path}")


def _source_for(mode: BuildMode, source: Path | None) -> Path:
    """Append has no default document. New may use the bundled template."""
    match mode:
        case BuildMode.APPEND:
            if source is None:
                raise PackageError("missing_source", "append requires --source")
            return source
        case BuildMode.NEW:
            return bundled_template() if source is None else source
        case unreachable:
            assert_never(unreachable)


if __name__ == "__main__":
    app()
