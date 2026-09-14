# Technical write-up

`pipeline_technical.tex` is the editable source and `pipeline_technical.pdf` is
its current rendered form. `response_validity_current.tex` is included by the
main source and should not be compiled as a competing report. Superseded source
and PDF snapshots are under `archive/`.

The current document distinguishes the 224,544-response, 18-model Luna v2.4
promoted release `canon_024` from the accepted but unpromoted 299,080-response,
24-model `canon_031` candidate. Earlier candidates, including `canon_029`, are
retained only as immutable provenance. It records the
exact OpenRouter, Hugging Face, native API, and NYU Torch access routes without
embedding secrets or private endpoint URLs. Publication figures are not embedded
here; their specifications and external legends live in
`docs/CANONICAL_ANALYSES.md` and `docs/CANONICAL_FIGURE_LEGENDS.md`.

The shortest complete account of execution order is
`docs/TECHNICAL_PIPELINE.md`. The PDF supplies the fuller methodological detail;
it should not be read as an operational runbook.

LaTeX auxiliary files are ignored and should be removed after a successful
build. Keep both the `.tex` source and final `.pdf`.
