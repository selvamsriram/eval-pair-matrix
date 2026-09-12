# Reproduce the camera-ready results

Run these commands from the repository root with Python 3.11 or newer. The
analysis uses saved data and makes no API/model calls. NumPy 2.3.5 was used for
the final checks; install it with `python3 -m pip install -r
paper/requirements-analysis.txt`.

```bash
python3 paper/audit/paired_audit.py
python3 paper/audit/behavior_stratified.py
python3 paper/behavior_paired_sensitivity.py
python3 paper/audit/judge_cost.py
```

The first three commands write derived JSON, CSV, Markdown and LaTeX outputs
under `paper/audit/` and `paper/tables/`. They do not edit manuscript sources or
raw records. Cost accounting prints JSON to stdout. The frozen human decisions
in `cell_review_progress.json` must not be overwritten or replaced by generated
judgments. `build_cell_review_queue.py` reconstructs the queue, not the decisions.

## Canonical inputs and expected outputs

| Component | Input / entry point | Check |
|---|---|---|
| Frozen pool | `data/exp/3provider_300.jsonl` and its manifest | 300 records; 275 pass all five gates; 25 diagnostics; selected perturbers 83 GPT / 92 Grok / 125 Gemini |
| Generation and labels | Three `05_label_eval.jsonl` paths in `audit/paired_audit_report.json` | 900 output slots; 897 populated evaluation fields; 896 nonempty answers |
| Judge matrix | Nine `06_judge.jsonl` paths in the same inventory | 2,683 verdicts |
| Paired analysis | `audit/paired_audit.py` | `paired_audit_report.json`, `paired_verdicts.csv`; global validated recall −0.5 pp [−2.7,+1.7], avoided-claim flagging −4.3 pp [−6.6,−2.0] |
| Behavior strata | `audit/behavior_stratified.py` | `behavior_stratified_report.json` |
| Existing paired sensitivity | `behavior_paired_sensitivity.py` | `tables/behavior_paired_sensitivity.json` and `.tex` |
| Human audit | `audit/cell_review_queue.json`, `cell_review_progress.json`, and Appendix D.1 | 88 of 153 verdict cases; 79 answers / 70 records; 25 apparent FPs comprise 22 alternate errors, 2 label mistakes, 1 unclear case |
| Cost | `audit/judge_cost.py`, `judge_usage.jsonl`, `judge_usage_manifest.json` | 2,688 calls; 2,683 verdicts; 5 failures; 5,626,958 input / 308,181 output tokens; 17,580,271 ms summed call time |

Paired analyses use 10,000 core-ID cluster-bootstrap replicates and seed
20260627. Defaults reproduce the published analyses. Setting `PAIRED_BOOTSTRAP`
or `PAIRED_SEED` changes the run; do not use reduced bootstrap counts for a
publication check. The behavior-stratified script uses its own documented
answer-level bootstrap and `BEHAVIOR_BOOTSTRAP` / `BEHAVIOR_SEED` settings.

The final release pass reproduced the paired report and flattened verdicts,
behavior report, sensitivity values/table, and audit queue from the saved raw
inputs. No new experiment or label sensitivity was added. Display rounding and
paper layout are maintained in the manuscript, rather than automatically
overwritten by generated tables.

## Portable cost accounting

`judge_usage.jsonl` is a projection of every event in the nine original judge
traces: run/event IDs, judge/generator model IDs, latency, recorded input/output
tokens, and a Boolean error indicator. It omits prompts, responses, and exception
bodies. Null token fields remain null. The manifest records the ledger hash and
the hashes of the original traces. The cost script reconciles event counts with
the saved verdicts and rejects duplicate events or unexpected model pairs.

When the original local traces are available, verify the independent input path:

```bash
python3 paper/audit/judge_cost.py --raw-traces > /tmp/cost-raw.json
python3 paper/audit/judge_cost.py > /tmp/cost-ledger.json
diff -u /tmp/cost-raw.json /tmp/cost-ledger.json
```

Both input modes produced byte-identical reports during the final check. Call
time is a sum, not wall-clock runtime. Tokens exclude unrecorded failed-call and
retry usage and Gemini thinking tokens; generation and dataset construction are
outside the reported judge totals.

## Packages

`python3 paper/package_camera_ready.py` produces a paper-source ZIP and a
reproducibility ZIP under `output/release/`, each with a SHA-256 manifest. The
reproducibility archive includes the frozen pool, manifest, three labeled-output
files, nine judge files, analysis code and outputs, human-review inputs, prompts,
schemas, and portable cost ledger. It excludes credentials, local traces,
temporary builds, historical drafts, and review PDFs. Packaging is local;
publication and repository visibility are separate actions.

Source data originates in GaRAGe. Retain upstream provenance and applicable
upstream terms when redistributing source passages; this package does not add
or change a data license.
