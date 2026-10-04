"""Manuscript fixtures for the harness checks."""

from __future__ import annotations

import json
from pathlib import Path


def manuscript(wide: Path, tall: Path) -> str:
    """Two figures, one equation, and one table."""
    payload = {
        "blocks": [
            {"type": "h", "level": 1, "text": "H1TOKEN"},
            {"type": "p", "text": "Body mentions Figure W and cites [R1]."},
            {
                "type": "figure",
                "id": "W",
                "mention": "Figure W",
                "asset": "wide",
                "source": "wide-source-token",
                "caption": "Figure W. wide-source-token.",
            },
            {"type": "p", "text": "Body mentions Figure T."},
            {
                "type": "figure",
                "id": "T",
                "mention": "Figure T",
                "asset": "tall",
                "source": "tall-source-token",
                "caption": "Figure T. tall-source-token.",
            },
            {"type": "eq", "lines": ["EQTOKEN = 1"]},
            {"type": "table", "headers": ["HCOL"], "rows": [["CELLTOKEN"]]},
        ],
        "references": [{"key": "R1", "text": "[R1] REFTOKEN"}],
        "assets": {"wide": {"path": str(wide)}, "tall": {"path": str(tall)}},
    }
    return json.dumps(payload)


def valid_spec(tmp: Path) -> Path:
    path = tmp / "valid.json"
    path.write_text(
        json.dumps(
            {
                "blocks": [
                    {"type": "p", "text": "See Figure F before the picture [R1]."},
                    {
                        "type": "figure",
                        "id": "F",
                        "mention": "Figure F",
                        "asset": "ok",
                        "source": "source-token",
                        "caption": "Figure F. source-token.",
                    },
                ],
                "references": [{"key": "R1", "text": "[R1] ref"}],
                "assets": {"ok": {"path": str(tmp / "ok.png")}},
            }
        ),
        encoding="utf-8",
    )
    return path


def figure_spec(tmp: Path, *, asset: str, previous: str, caption: str) -> Path:
    path = tmp / f"fig-{Path(asset).name}.json"
    path.write_text(
        json.dumps(
            {
                "blocks": [
                    {"type": "p", "text": previous},
                    {
                        "type": "figure",
                        "id": "F",
                        "mention": "Figure F",
                        "asset": "ok",
                        "source": "source-token",
                        "caption": caption,
                    },
                ],
                "assets": {"ok": {"path": asset}},
            }
        ),
        encoding="utf-8",
    )
    return path


def ref_spec(tmp: Path, *, cite: bool, extra: str = "") -> Path:
    path = tmp / f"ref-{cite}-{extra}.json"
    body = "Cited [R1]." if cite else "No citation here."
    path.write_text(
        json.dumps(
            {
                "blocks": [{"type": "p", "text": f"{body} {extra}".strip()}],
                "references": [{"key": "R1", "text": "[R1] ref"}],
            }
        ),
        encoding="utf-8",
    )
    return path
