# Eval-Pair Matrix

**Eval-Pair Matrix: Answer-Paired Meta-Evaluation of LLM Judges for Grounded RAG**
Sriram Selvam and Anneswa Ghosh · Independent Researchers

Accepted at GroundLM 2026; the authors have submitted the camera-ready version.
The protocol evaluates a crossed matrix of generators and blind judges, pairing
judges on the same candidate answer to estimate matching-model effects.

## Paper and artifacts

- [Submitted camera-ready paper](output/pdf/eval-pair-matrix-camera-ready.pdf)
- [Changes highlighted against the original submission](output/pdf/eval-pair-matrix-all-changes.pdf)
- [Paper sources and build instructions](paper/README.md)
- [Reproduce the reported analyses](paper/REPRODUCIBILITY.md)
- [Submission snapshot and verification](docs/submission.md)
- [Source ZIP](output/release/eval-pair-matrix-camera-ready-source.zip) · [Reproducibility ZIP](output/release/eval-pair-matrix-reproducibility.zip)

The frozen experiment has 300 records (275 validated, 25 diagnostics), three
generators, and 2,683 judge verdicts. The aggregate paired recall contrast is
−0.5 percentage points. The −4.3-point avoided-claim flagging contrast is not a
false-alarm-rate estimate; see the paper for endpoint differences and audit scope.

## Reproduce saved-data analyses

Requires Python 3.11 or newer. These commands make no model calls.

```bash
python3 -m pip install -r paper/requirements-analysis.txt
python3 paper/audit/paired_audit.py
python3 paper/audit/behavior_stratified.py
python3 paper/behavior_paired_sensitivity.py
python3 paper/audit/judge_cost.py
```

To build the paper with pdfLaTeX:

```bash
bash paper/build_camera_ready.sh
```

Rebuilt PDFs and packages go under ignored `tmp/`; `output/` preserves the
submitted files. Analysis commands write derived reports as described in the
[reproducibility guide](paper/REPRODUCIBILITY.md).

## Run new experiments

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env
```

Configure provider credentials in `.env`, then follow the
[CLI and development guide](docs/cli.md). The command is named `perturb`.

## Repository map

| Directory | Contents |
|---|---|
| `src/perturb/` | Pipeline, providers, prompts, schemas, and viewer |
| `data/` | Frozen pools and saved experimental runs at their original paths |
| `paper/` | Final manuscript, referenced figures, analyses, and build tools |
| `output/` | Preserved submitted PDFs, release ZIPs, and verification records |
| `docs/` | CLI guide, submission record, and repository guide |
| `archive/` | Prior drafts, reviews, research notes, and figure development |

See the [repository guide](docs/repository.md) and [archive index](archive/README.md).
