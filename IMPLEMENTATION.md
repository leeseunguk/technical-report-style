# Implementation evidence

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

## Contract now

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
