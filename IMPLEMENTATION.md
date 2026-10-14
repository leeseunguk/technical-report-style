# Implementation evidence

## 2026-10-06: source and equation explanation

`EquationBlock.source` and `TableBlock.source` are required strings
(`min_length` 1). This is a deliberate contract change. `--ledger` is optional.

- After one equation, or a run of consecutive equations, the next block must be a body paragraph. Error: `missing_equation_explanation`.
- A line that contains `(N)` needs that number in some paragraph before the next heading. `식 (N)` is accepted because it contains `(N)`.
- An equation `source` must appear in that following body paragraph. Error: `missing_equation_source`.
- A table `source` must appear in the paragraph immediately before or after the table. Error: `missing_table_source`.
- Equation, table, and figure sources must contain a known reference `cite`, a local file that exists, or one of `이 문서`, `이 교재`, `본 연구`, `this document`. Unknown author-year spans are `missing_reference`. A path token that does not exist is `missing_source_file`. A source with none of the three is `unsourced`.
- Path tokens are absolute paths, or relative paths that contain `/` and an extension. They resolve from the manuscript directory. URLs are not path tokens.
- `--ledger PATH` reads a JSON list and does not render it. Each numbered equation (`eq:N`), figure (`fig:<id>`), and table (`table:<n>`, 1-based) needs an entry or the build fails with `missing_ledger_entry`. `checked_against.pdf` or `checked_against.file` must exist (`missing_source_file`). `kind` `literature` or `adapted` needs a citation that matches a reference (`missing_reference`). `status` `unverified` needs `확인하지 못` or `not verified` in the item's in-text source (`unverified_claimed`).
- The CLI does not open a PDF to check that a cited page or equation number is correct. A reviewer still does that.

Example:

```bash
python3 /home/lsu1080/.omo/agent/skills/technical-report-style/scripts/build_report.py \
  --manuscript /home/lsu1080/.omo/agent/skills/technical-report-style/examples/manuscript.json \
  --ledger /home/lsu1080/.omo/agent/skills/technical-report-style/examples/source_ledger.json \
  --output /tmp/report-style-example.docx --mode new
```

## 2026-10-06: native Word math

현재 `eq.lines`는 필수 문자열 목록, `eq.latex`는 선택 문자열 목록이다.
`latex`를 주면 `lines`와 줄 수가 같아야 하며 비어 있는 항목은 거부한다.
분수·근호·첨자·지수·합·적분의 구조가 필요한 식에는 이 변환 입력을 준다.
변환 원문은 독자에게 출력하지 않고 `m:oMathPara/m:oMath`로 삽입한다.
`lines`만 주는 단순 선형식은 네이티브 `m:t`에 그대로 유지한다.
이 경로는 `/`, `^`, `sqrt`를 자동 구조 해석하지 않으므로 복잡한 식에 사용하지 않는다.
변환 실패는 출력 파일을 쓰지 않는 오류이며 평문 폴백이 없다.
제곱근 차수 노드와 빈 합·적분 한계 표시를 보정한다.

의존성 `lxml`, `latex2mathml`, `mathml2omml`은 `build_report.py`와
`check_harness.py`의 PEP 723에 선언했다. 현재 환경의 하네스 18개 검사 그룹은
종료코드 0이었다. 네이티브 선형 입력 보존, 구조화 수식, 불지원 입력 거부,
append 원본 보존을 포함한다. 마지막 경계 정리 뒤 네이티브 두 그룹도 통과했다.
이 기록은 Word GUI에서 클릭·편집한 시연이나 원고 내용의 과학적 검증이 아니다.
아래 2026-10-05 평문 출력 기록은 과거 증거로만 읽는다.

Corrected the generic harness to the textbook at
`/mnt/c/Users/user/Downloads/burst_fp_textbook (2)/build/burst_fp_textbook.docx`.
The previous Letter/blue continuation is not the style source. No commit or push.
The textbook file was not modified.

Parent verification after this worker handoff also added native `Block Text`
callout roles (`callout-title`, `callout-body`) and a real-CLI regression check.
The complete 14-group harness passed. The final Korean example was rendered
and directly inspected as one A4 page, with both shaded callouts, black headings,
table, figure, caption, author-year citation and reference. Its artifacts are
`gs_fast/artifacts/burst_fp_qtn_continuation_20261005/harness_example_final.docx`
and `harness_render_final/harness_example_final.pdf`.
The worker's earlier 13-group output and earlier example hash below remain
historical evidence, not fingerprints of that final example.

## Execution

Session log:
`/mnt/c/Users/user/Documents/Private/GSR/.omo/senpi-task/children/st_01a10a7d/sessions/st_01a10a7d/2026-10-05T05-15-37-090Z_01a10a7d-2902-73b4-9d05-482bcfe1f56c.jsonl`

- `model_change`: provider `xai`, modelId `grok-4.7`, timestamp `2026-10-05T05:15:38.613Z`
- `thinking_level_change`: `thinkingLevel` `xhigh`, `thinkingSelection.source` `explicit`, id `fbd1ad72`
- Process environment: `PI_MODEL=grok-4.7`, `PI_PROVIDER=xai`, `PI_REASONING_LEVEL=xhigh`

This is Grok 4.7 xhigh. `apply_patch` is not in the active tool catalog
(`tool_search` returned no match), so source edits used the active file tools.
No type ignore and no package install.

## Source measurement

SHA256: `165b6a8a768d86f27e10e964f8eabfec44560923030112adb0d3fa707d9cfdd4`

The same hash was recorded before extraction and after the example build.

| Item | Measured value |
|---|---|
| Page | A4, `pgSz` w=11906 h=16838 twips (21.001 × 29.700 cm) |
| Margins | top/right/bottom/left 1417 twips (2.499 cm) |
| Header/footer | 709 twips (1.250 cm) |
| Body | Malgun Gothic 10.5 pt, line 336 (`lineRule=auto`, 1.4), after 120 |
| Heading 1 / 2 | 16 pt / 13 pt, bold, color `000000` |
| Caption | style `Caption`, 9.5 pt, regular, color `222222`, centered |
| Table | style id `Table` |
| Theme | latin, ea, and cs are Malgun Gothic |
| Source shape | chapters 1–9 plus appendix and references; caption numbers 1–45 |

Those chapter and figure counts describe the source. They are not runtime quotas.
The template extract dropped body text and media. Source media count in the
template is 0. Source hash was unchanged (`SOURCE_UNCHANGED True`).

## Commands and results

Extract, exit 0:

```bash
python3 /home/lsu1080/.omo/agent/skills/technical-report-style/scripts/extract_style_template.py \
  --source "/mnt/c/Users/user/Downloads/burst_fp_textbook (2)/build/burst_fp_textbook.docx" \
  --output /tmp/burst-fp-style-template.docx
```

`PG 11906 16838`; margins `1417 1417 1417 1417 709 709`; styles
`Normal`, `Heading1`, `Heading2`, `Caption`, `Table`, `BodyText` present;
`MEDIA 0`; `TEMPLATE_OK`.

Installed that file as `template/report-style.docx`.
Template SHA256: `e8c196b721cb3a0c38e0f27efabbdf635b9786f47efdce381afc13eb0ada50b2`.

Harness, exit 0:

```bash
python3 /home/lsu1080/.omo/agent/skills/technical-report-style/scripts/check_harness.py
```

```text
PASS help
PASS new
PASS reuse
PASS append
PASS plain
PASS reject
PASS append-source
PASS windows-path
PASS literal-index
PASS latex-equation
PASS author-year
PASS author-year-missing
PASS numbered-style
```

Example, exit 0:

```bash
python3 /home/lsu1080/.omo/agent/skills/technical-report-style/scripts/build_report.py \
  --manuscript /home/lsu1080/.omo/agent/skills/technical-report-style/examples/manuscript.json \
  --output /home/lsu1080/.omo/agent/skills/technical-report-style/examples/example_new.docx \
  --mode new
```

`WROTE` that path. Output SHA256:
`93f1d667596fedc09e5f792a2910b3a1c38e39bb929d0a4dc509740ac9061d9b`.
Audit: `styles_unchanged` true, `section_geometry_unchanged` true, page
`11906×16838`, margins `1417`. Caption paragraph uses `Caption`. Body keeps
`(Style Note, 2026)` and does not contain `[StyleNote2026]`. `EXAMPLE_OK`.

Language-server check on `scripts/render.py` after the edits reported only the
pre-existing implicit-relative-import notes that also appear on unchanged
script files. No new error was left in the changed logic.

## 2026-10-05 당시 계약

이 절은 당시 실행의 기록이다. 2026-10-06부터 수식 정책은 편집 가능한
OMML이므로 아래의 예전 평문·LaTeX 거부 동작을 현재 계약으로 사용하지 않는다.

- New documents inherit the textbook template. The renderer does not paint the
  old 11 pt / 8 pt body, 9 pt italic `#444444` caption, or Light Grid table.
- Headings use the source heading style with no direct size.
- Body uses `Body Text` when the source has it and does not override spacing.
- Tables write style id `Table` explicitly. python-docx would otherwise omit
  the default table style. `Light Grid Accent 1` remains only as a fallback
  when that is the style the source actually has.
- Pictures stay within 15.5 cm by 17 cm, and within the source content width
  if that is narrower. Picture paragraphs are centered, keep-with-next, before
  4 pt, after 2 pt.
- Captions use `Caption` and regular (not italic) runs. A source without that
  style gets 9.5 pt regular `#222222`, not the old italic caption.
- `citation_style: author-year` uses each reference `cite` string. It does not
  require `[key]`. Omitted style uses author-year when the manuscript is not
  already numbered. Explicit `numbered` still requires `[key]`.
- `samples[0]`, chained indexing, and Windows paths in prose stay literal.
  Equation blocks still reject LaTeX markers.
- Append still preserves source body, media, and styles, and still refuses
  overwrite. It does not restyle the original package.

## Changed files

- `README.md`
- `SKILL.md`
- `IMPLEMENTATION.md`
- `examples/manuscript.json`
- `references/polishing.md`
- `references/style.md`
- `references/workflow.md`
- `scripts/check_harness.py`
- `scripts/check_style.py`
- `scripts/manuscript.py`
- `scripts/render.py`
- `template/report-style.docx`

`examples/example_new.docx` and its audit JSON were regenerated. `*.docx`
except the template, and `*.audit.json`, are gitignored.

## Limitations

- Chapter phrases and continuous figure numbers are authoring rules. The CLI
  does not require the Korean phrases and does not renumber figures.
- Author-year checking is an exact `cite` substring in a body paragraph, not a
  general AGU parser.
- The CLI does not run hybrid capture, Astra review, or im-not-ai. Those stay
  in the skill procedure.
- New mode keeps the final section properties. Word pagination is not rendered
  here. python-docx prints a UserWarning when it resolves `Caption` by style
  id; the style is still applied.
- There is no overwrite switch. No commit was created.

## 2026-10-05: prose checker and rewrite lessons

The lead rewrote the reviewer-written QTN continuation (chapters 10–15) with the
same figures, equations, tables, references and protected numbers. The comparison
is recorded in `references/writing-lessons.md` and turned into rules in `SKILL.md`,
`references/workflow.md` and `references/polishing.md`.

New `scripts/check_prose.py MANUSCRIPT.json|DRAFT.md`:

- errors (exit 1): ungrammatical present-tense endings on vowel or ㄹ stems
  (빼는다, 쓰는다), exact duplicate paragraphs;
- warnings: negative endings above 20% of body sentences, the same provenance or
  scope disclaimer more than three times, paragraphs that differ only in numbers.

`figure_ledger`, `references`, `assets` and `reference_heading` are skipped so a
ledger copy of a caption is not a duplicate. On the reviewer manuscript it reports
2 errors and negation 24%; on the rewrite it reports `PROSE_OK` and 16%.
The harness adds `prose-check` (15 groups, all PASS). The checker does not judge
meaning, science or tone beyond these patterns.
