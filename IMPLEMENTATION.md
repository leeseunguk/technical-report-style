# Report style harness

Installed at `/home/lsu1080/.omo/agent/skills/technical-report-style/`.
The parent reran the checks from this final path: all ten groups passed,
and language-server diagnostics across the 13 Python files reported zero errors.

Model: `grok-4.7`, provider `xai`, reasoning `xhigh`. No routing mismatch.
`apply_patch` is registered but inactive for this model, so source files were
written with the active file tools. No type ignore and no package install.

## Commands

```bash
python3 /home/lsu1080/.omo/agent/skills/technical-report-style/scripts/build_report.py --help

python3 /home/lsu1080/.omo/agent/skills/technical-report-style/scripts/build_report.py \
  --manuscript /home/lsu1080/.omo/agent/skills/technical-report-style/examples/manuscript.json \
  --output ./my-report.docx \
  --mode new

python3 /home/lsu1080/.omo/agent/skills/technical-report-style/scripts/check_harness.py
```

`--source` defaults to `template/report-style.docx` for `new` only. `append`
requires `--source` and exits 2 with `missing_source` if it is omitted. It does
not append to the bundled template. Overwrite is rejected. An output path that
is the source, manuscript, audit, or a figure asset is rejected. Inputs are not
modified.

Regenerate the bundled template from a style source, without writing a binary
by hand:

```bash
python3 /home/lsu1080/.omo/agent/skills/technical-report-style/scripts/extract_style_template.py \
  --source STYLE_SOURCE.docx \
  --output ./my-style-template.docx
```

The illustrative fixture is generated, not measured:

```bash
python3 /home/lsu1080/.omo/agent/skills/technical-report-style/scripts/make_illustrative.py
```

## Manuscript

Blocks are `h`, `p`, `eq`, `table`, and `figure`. `references`, `assets`, and
`reference_heading` may be omitted. A note with no papers and no figures is
valid. When a figure is present it needs an id, an explicit mention that
contains that id, a caption containing the mention and the source string, and
an immediately preceding paragraph that contains the mention. The asset file
must exist and open as an image. When a reference is present, a body paragraph
must cite `[key]`. A standalone citation with no entry is rejected. Brackets
immediately following an identifier or another closing bracket, such as
`samples[0]` or `matrix[row][col]`, are literal indexing, not citations.
Separate actual citations from identifiers with whitespace. Backslash and
`$$` are rejected only inside `eq` blocks so equations stay editable linear
text; ordinary prose may contain paths such as `C:\data\input.csv`.

Asset paths are relative to the manuscript file unless absolute.

## Style contract

The renderer does not redefine styles.

- Headings use the source Heading style and no direct size.
- Body paragraphs inherit 11 pt and set space-after to 8 pt.
- Equations are centered 11 pt italic text runs, not OMML.
- Tables use Light Grid Accent 1 at 9 pt when a table is present. The style
  must already exist.
- Pictures keep aspect ratio inside 15.1 cm by 17 cm. The picture paragraph
  uses keep-with-next so the caption follows it. The caption is Normal text,
  9 pt italic `#444444`, not the Caption style.
- Append inserts a page break before the new blocks. The manuscript states the
  added scope. No topic sentence is hardcoded.
- New mode keeps the final section geometry and the style and theme parts,
  and removes old body text, media, thumbnail, and non-style parts.

## Audit

A successful build writes `<output>.audit.json`. Append reports
`allowed_changed_parts` (`word/document.xml`,
`word/_rels/document.xml.rels`, `[Content_Types].xml`, `docProps/app.xml`,
`docProps/core.xml`) and fails if any other original part changes, any original
part is removed, or a non-media part is added. Original media parts must keep
their names and bytes. New mode fails if source media remains unless that exact
file hash was requested by a figure. Requested images must be embedded.

## Observed verification

`check_harness.py` passed `help`, `new`, `reuse`, `append`, `plain`, `reject`,
`append-source`, `windows-path`, `literal-index`, and `latex-equation`.
Append without `--source` exits 2 with `missing_source`
and writes no file. The no-excuse checker reported no violations. The example build
embedded `examples/illustrative.png`, preserved styles, theme, and section
geometry, and reported no source-text leak. The style source used to generate
the template was not modified.

The final installation has zero language-server error diagnostics across all
13 Python files. No ignore comment was added.

## Limitations

- New mode keeps the final section properties. Earlier section breaks are body
  content and are removed.
- Same-page placement is keep-with-next plus the size cap. Word pagination is
  not rendered here.
- Non-square image DPI does not change the placed size. Width and height are
  set from pixel aspect ratio.
- There is no overwrite switch.
