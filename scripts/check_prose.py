#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

# ─── How to run ───
# python3 check_prose.py MANUSCRIPT.json [--json]
# python3 check_prose.py DRAFT.md

"""Mechanical Korean prose checks for textbook manuscripts.

Errors (exit 1) are defects a reader sees immediately: an ungrammatical
present-tense ending after a vowel or ㄹ stem (빼는다, 쓰는다, 만들는다) and
duplicated paragraphs. Warnings flag drafting habits that made reviewer-written
chapters hard to follow: prose that defines things mostly by negation, and the
same provenance disclaimer repeated in body paragraphs. Warnings are evidence
for a rewrite, not proof of bad prose, and none of these checks judges meaning.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

HANGUL_BASE: Final = 0xAC00
HANGUL_LAST: Final = 0xD7A3
JONG_COUNT: Final = 28
JONG_RIEUL: Final = 8
NEGATIVE_END: Final = re.compile(r"(?:않는다|않았다|아니다|없다|못한다)[.)]?$")
SENTENCE_SPLIT: Final = re.compile(r"(?<=[다요음])[.?!]\s+|\n+")
BAD_PRESENT: Final = re.compile(r"([가-힣])는다(?=[.,)\s]|$)")
DISCLAIMERS: Final = ("새 피팅이 아니다", "새 적합이 아니다", "다시 조판", "여기서 정하지 않는다", "여기서 다시 판정하지 않는다")
NEGATION_WARN: Final = 0.20
DISCLAIMER_WARN: Final = 3
MIN_DUP_CHARS: Final = 60
SKIPPED_KEYS: Final = frozenset({"figure_ledger", "references", "assets", "reference_heading"})
CAPTION_START: Final = re.compile(r"^(그림|표|Figure|Table)\s*[\w.()-]+\.")
DIGITS: Final = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True, slots=True)
class Finding:
    level: str
    code: str
    detail: str


def has_final(char: str, *, rieul_counts: bool) -> bool:
    """True when a Hangul syllable has a final consonant. ㄹ is treated as open when asked."""
    code = ord(char)
    if not HANGUL_BASE <= code <= HANGUL_LAST:
        return True
    jong = (code - HANGUL_BASE) % JONG_COUNT
    if jong == 0:
        return False
    return rieul_counts or jong != JONG_RIEUL


def paragraphs(path: Path) -> list[tuple[str, str]]:
    """(kind, text) pairs. kind is body or caption. Ledger and reference subtrees are skipped."""
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() != ".json":
        parts = [part.strip() for part in re.split(r"\n\s*\n", raw) if part.strip() and not part.lstrip().startswith(("![", "|", "#"))]
        return [("caption" if CAPTION_START.match(part) else "body", part) for part in parts]
    found: list[tuple[str, str]] = []

    def walk(value: object, key: str) -> None:  # noqa: OBJECT_OK - JSON boundary
        match value:
            case str() if key in {"text", "learning", "summary"}:
                found.append(("body", value))
            case str() if key == "caption":
                found.append(("caption", value))
            case list():
                for item in value:
                    walk(item, key)
            case dict():
                for name, item in value.items():
                    if str(name) not in SKIPPED_KEYS:
                        walk(item, str(name))
            case _:
                return

    walk(json.loads(raw), "")
    return found


def sentences(texts: list[str]) -> list[str]:
    out: list[str] = []
    for text in texts:
        out.extend(part.strip() for part in SENTENCE_SPLIT.split(text) if part.strip())
    return out


def bad_present_forms(texts: list[str]) -> list[str]:
    """빼는다/쓰는다/만들는다 are wrong; correct forms are 뺀다/쓴다/만든다."""
    hits: list[str] = []
    for text in texts:
        for match in BAD_PRESENT.finditer(text):
            stem = match.group(1)
            if not has_final(stem, rieul_counts=False):
                start = max(0, match.start() - 8)
                hits.append(text[start : match.end() + 1].strip())
    return hits


def duplicate_paragraphs(texts: list[str], *, ignore_numbers: bool) -> list[str]:
    """Exact repeats, or with ignore_numbers, paragraphs that differ only in numbers."""
    seen: dict[str, int] = {}
    dups: list[str] = []
    for text in texts:
        key = re.sub(r"\s+", " ", text).strip()
        if ignore_numbers:
            key = DIGITS.sub("#", key)
        if len(key) < MIN_DUP_CHARS:
            continue
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            dups.append(key[:80])
    return dups


def check(items: list[tuple[str, str]]) -> list[Finding]:
    texts = [text for _kind, text in items]
    body_texts = [text for kind, text in items if kind == "body"]
    exact = duplicate_paragraphs(texts, ignore_numbers=False)
    findings = [Finding("error", "bad_present_form", hit) for hit in bad_present_forms(texts)]
    findings += [Finding("error", "duplicate_paragraph", dup) for dup in exact]
    near = [dup for dup in duplicate_paragraphs(body_texts, ignore_numbers=True) if dup not in exact]
    findings += [Finding("warning", "near_duplicate_paragraph", dup) for dup in near]
    sents = sentences(body_texts)
    if sents:
        negative = sum(1 for sentence in sents if NEGATIVE_END.search(sentence))
        ratio = negative / len(sents)
        if ratio > NEGATION_WARN:
            findings.append(Finding("warning", "negation_heavy", f"{negative}/{len(sents)} = {ratio:.0%} > {NEGATION_WARN:.0%}"))
    body = "\n".join(body_texts)
    for phrase in DISCLAIMERS:
        count = body.count(phrase)
        if count > DISCLAIMER_WARN:
            findings.append(Finding("warning", "repeated_disclaimer", f"'{phrase}' x{count}"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Mechanical Korean prose checks for textbook manuscripts.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.path.is_file():
        print(f"missing input: {args.path}", file=sys.stderr)
        return 2
    findings = check(paragraphs(args.path))
    if args.json:
        print(json.dumps([asdict(item) for item in findings], ensure_ascii=False, indent=1))
    for item in findings:
        print(f"{item.level.upper()} {item.code}: {item.detail}")
    errors = [item for item in findings if item.level == "error"]
    print("PROSE_OK" if not errors else f"PROSE_FAIL {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
