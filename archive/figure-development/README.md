# Figure development archive

`figures/` holds figures not referenced by the submitted manuscript, PNG previews,
alternate layouts, and recovery copies. `generate_figures.py` and `fix_figures.py`
are historical plotting scripts, preserved verbatim. They use manually recorded
values and can overwrite figure PDFs; they are not current build entry points.
Replay them from a historical checkout if needed.

The ten referenced final PDFs and three existing Graphviz sources remain in
[paper/figures](../../paper/figures/). Their hashes are recorded in the
[submission manifest](../../docs/submission-manifest.json).
`paper/generate_composition_figure.py` remains alongside the active paper because
it derives composition plots from the frozen pool; the paper build uses the
already-preserved PDF figures.
