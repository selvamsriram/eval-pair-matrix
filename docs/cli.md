# CLI and development guide

Run commands from the repository root. The final paper uses `data/exp/3provider_300.jsonl`; commands using `exp-300-perturbed` illustrate the earlier pipeline. See [reproducibility](../paper/REPRODUCIBILITY.md) for the exact published inputs and [historical experiments](../archive/research-notes/experiments.md) for older runs.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env       # fill in AZURE_GPT_* (and any other providers you want)
```

The CLI installs at `.venv/bin/perturb`. Activate the venv or call the binary directly.

---

## Commands

Every command is implemented in [src/perturb/cli.py](../src/perturb/cli.py).
Subcommands grouped by purpose below; each has `--help` for the full flag list.

### Data ingestion

#### `perturb fetch`
Download GaRAGe from HuggingFace to `data/raw/garage_<split>.jsonl`. One-shot;
no API calls. ([src/perturb/fetch.py](../src/perturb/fetch.py))

```bash
perturb fetch                       # full train split (~2,366 rows)
perturb fetch --limit 200           # smoke runs / faster iteration
perturb fetch --split test          # different split
perturb fetch --out data/raw/my.jsonl
```

### Curated experimental datasets (frozen)

#### `perturb exp build <name> --source <raw.jsonl> --n 300`
Apply gates + stratified sampling **once** and freeze the result to
`data/exp/<name>.jsonl` (plus a `.manifest.json` sidecar with seed, sample_ids,
realized strata, gate-pass counts). Records are written in stratified
round-robin order so any contiguous slice stays balanced.
([src/perturb/exp.py](../src/perturb/exp.py))

```bash
perturb exp build exp-300 \
  --source data/raw/garage_train.jsonl \
  --n 300 --seed 17
```

Why: pipelines later **dip into** this frozen file with `--take/--offset`, so
multiple runs over time use the same canonical pool with no collisions and no
re-sampling drift.

#### `perturb exp combine <name> --from PATH --from PATH ... --order round-robin`
Merge multiple finished-pipeline JSONLs (typically each step's `03_validate.jsonl`)
into one frozen dataset. With `--order round-robin`, any contiguous slice of
the output draws evenly from each input — so a Phase 2 `--take 30` from
`exp-300-perturbed` automatically pulls 10 records perturbed by each model.

```bash
perturb exp combine exp-300-perturbed \
  --from data/runs/20260530-120201-100q-first/03_validate.jsonl \
  --from data/runs/20260530-142314-100q-grok/03_validate.jsonl \
  --from data/runs/20260530-162330-100q-gemini/03_validate.jsonl \
  --order round-robin
```

Other orders: `sequential` (concat) and `shuffle` (seeded random union).

#### `perturb exp ls`
List built exp datasets.

#### `perturb exp show <name>`
Print the manifest (seed, source, strata, full `sample_ids` list).

### Pipeline

#### `perturb runs new --name <label>`
Mint a fresh run id and directory under `data/runs/`. ([src/perturb/run.py](../src/perturb/run.py))

```bash
RUN=$(perturb runs new --name 100q | grep run_id | awk '{print $2}')
```

#### `perturb pipeline --run <id> --source <jsonl> --model <provider>`
Run all three steps in order against one run id. Live progress bar per step.
([cli.py:pipeline](../src/perturb/cli.py))

Two source modes — the filter step auto-detects which:

```bash
# Build-from-raw: filter, sample, stratify, then perturb + validate
perturb pipeline --run "$RUN" \
  --source data/raw/garage_train.jsonl \
  --n 100 --model azure-gpt

# Exp-slice: dip into a frozen exp dataset, no resampling
perturb pipeline --run "$RUN" \
  --source data/exp/exp-300.jsonl \
  --take 100 --offset 0 \
  --model azure-gpt

# Stop early after a specific step (useful for audit/iteration)
perturb pipeline --run "$RUN" --source ... --model azure-gpt --stop-after perturb
```

Non-colliding slices of the same exp set:

```bash
perturb pipeline --run runA --source data/exp/exp-300.jsonl --take 100 --offset 0   --model azure-gpt
perturb pipeline --run runB --source data/exp/exp-300.jsonl --take 100 --offset 100 --model azure-gpt
perturb pipeline --run runC --source data/exp/exp-300.jsonl --take 100 --offset 200 --model azure-gpt
```

### Individual steps

Each is a thin shell over the same `_run_step_with_progress` helper. Useful
when you want to inspect intermediate output before paying for the next LLM
call.

#### `perturb filter --run <id> --source <jsonl>`
Gate + stratify (raw mode) or passthrough-slice (exp mode). No LLM.
Gates in [filter_step.py:_passes_gates](../src/perturb/steps/filter_step.py);
stratification in [filter_step.py:_stratify](../src/perturb/steps/filter_step.py).

```bash
perturb filter --run "$RUN" --source data/raw/garage_train.jsonl --n 100 --seed 17
perturb filter --run "$RUN" --source data/exp/exp-300.jsonl --take 100 --offset 0
```

Gates applied (raw mode only): `question_valid`, `question_seeking`,
`!question_false_premise`, `answer_validate`, and ≥2 grounding passages with
`evidence_correct=ANSWER-THE-QUESTION`.

#### `perturb perturb --run <id> --model <provider>`
Single LLM call per record: pick one answer-causal atomic value present in
both the answer and the grounding, propose a perturbed value from the closed
type menu, return full rewritten passage text for every mentioned passage. Plus
a deterministic leakage backstop on passages we did NOT send to the model.
([src/perturb/steps/perturb_step.py](../src/perturb/steps/perturb_step.py))

```bash
perturb perturb --run "$RUN" --model azure-gpt
perturb perturb --run "$RUN" --model azure-gpt \
  --types entity_substitution,temporal_shift,numerical_shift
```

Sends to the model: `ANSWER-THE-QUESTION` + `RELATED-INFORMATION` passages.
Closed menu of 10 perturbation types defined in
[schemas.py:PERTURBATION_TYPES](../src/perturb/schemas.py).

#### `perturb validate --run <id> --model <provider>`
LLM audit of 5 gates + plausibility, plus a deterministic leakage re-check
that **overrides** the LLM's `no_original_answer_leakage` gate if our scan
finds the original value anywhere in the perturbed grounding.
([src/perturb/steps/validate_step.py](../src/perturb/steps/validate_step.py))

```bash
perturb validate --run "$RUN" --model azure-gpt
```

The 5 gates: `type_valid`, `answer_causal`, `global_context_consistent`,
`no_original_answer_leakage`, `original_contradicts_perturbed`. Definitions in
[prompts.py:VALIDATE_SYSTEM](../src/perturb/prompts.py).
Pass criterion = all 5 True. Failed-validation records are **kept** in the
output (with `pipeline_state["validate"] == "failed:validation"` and detailed
`rejection_reasons`) so downstream generator experiments can use them.

### Audit + introspection

#### `perturb stats <run_id>` / `perturb stats <run_id> --detailed`
Per-step ok/failed/skipped counts and validation pass rate. With `--detailed`:
per-gate pass rate, perturbation-type distribution, plausibility breakdown,
top rejection-reason clusters. ([cli.py:stats](../src/perturb/cli.py))

```bash
perturb stats 20260530-002634-live-10-v3
perturb stats 20260530-002634-live-10-v3 --detailed
```

#### `perturb inspect <run_id> --step <name> [--core-id X | --index N]`
Pretty-print one record from a step's output JSONL.

```bash
perturb inspect $RUN --step perturb --index 0
perturb inspect $RUN --step validate --core-id garage_core_640d87e741e6
```

#### `perturb traces <run_id> --step <name> --tail N`
Print the last N LLM trace events for a step: model, latency, tokens, error.

```bash
perturb traces $RUN --step perturb --tail 5
```

Full traces (system prompt, user prompt, raw response, parsed JSON) live in
`data/traces/<run_id>/<step>.jsonl` — the viewer is the better way to browse them.

#### `perturb viewer --port 7437`
Launch the web trace viewer. Auto-picks the latest run, live-updates via SSE
when any step writes to disk, browsable tabs per record: Overview, Original,
Perturbed, Diff, Modifications, Validation, Traces. ([src/perturb/viewer/](../src/perturb/viewer/))

```bash
perturb viewer                       # http://127.0.0.1:7437
perturb viewer --port 8080
perturb viewer --reload              # dev mode, hot-reload on code changes
```

#### `perturb runs ls` / `perturb runs show <id>`
List runs (newest first, with which steps have completed); print a run's manifest.

#### `perturb models`
List registered LLM provider adapters and whether each is configured
(checks env vars). ([src/perturb/providers/](../src/perturb/providers/))

```bash
perturb models
# name        status         model
# azure-gpt   ready          gpt-5.4
```

---

## Example recipe for a new perturbation run

```bash
# 1. one-time: pull data + freeze the experimental set
perturb fetch
perturb exp build exp-300 --source data/raw/garage_train.jsonl --n 300

# 2. open the viewer in a second terminal
perturb viewer    # http://127.0.0.1:7437

# 3. run a 100-record slice with a chosen perturber
RUN=$(perturb runs new --name 100q-gemini | grep run_id | awk '{print $2}')
perturb pipeline --run "$RUN" --source data/exp/exp-300.jsonl \
  --take 100 --offset 200 --model gemini

# 4. inspect
perturb stats "$RUN" --detailed
perturb inspect "$RUN" --step validate --index 0

# 5. if anything crashes mid-run, resume — skips records already in the output
perturb pipeline --run "$RUN" --source data/exp/exp-300.jsonl \
  --take 100 --offset 200 --model gemini --resume
```

**Historical disjoint-slice example** (not the final paper pool):

```bash
# slice [0:100]   with GPT-5.4
# slice [100:200] with Grok 4.3
# slice [200:300] with Gemini 3.5 Flash
# each run is independent; records carry generators[step] provenance.
```

---

## How the pipeline works

```
                                                              data/runs/<id>/
                                                              ┌────────────────────┐
raw GaRAGe ──► filter ──► perturb ──► validate                │ 01_filter.jsonl    │
                  ▲           │           │                   │ 02_perturb.jsonl   │
                  │           ▼           ▼                   │ 03_validate.jsonl  │
            exp slice    LLM + det.  LLM + det. leak override │ manifest.json      │
            (no LLM)     backstop                             └────────────────────┘
                             │                                data/traces/<id>/
                             └──────────┬──────────►          ┌────────────────────┐
                                        ▼                     │ perturb.jsonl      │
                                  one trace event             │ validate.jsonl     │
                                  per LLM call                └────────────────────┘
```

- **One growing record per question**: a `CoreRecord`
  ([src/perturb/schemas.py](../src/perturb/schemas.py)) is created by `filter`
  and progressively populated by each subsequent step. Fields not yet
  populated are `None` / empty list. `pipeline_state[<step>]` records the
  per-step outcome (`ok`, `failed:<reason>`, `skipped:<reason>`).
- **No char offsets** in perturbations: the model returns full rewritten
  passage text + the swapped span as plain strings. LLMs are unreliable at
  exact offsets; we sidestep the problem.
- **Two leakage backstops**:
  - `perturb` step: deterministic regex sweep (whitespace + punctuation
    normalized) across all passages — if the original value still appears,
    the record is flagged `failed:leakage`.
  - `validate` step: re-runs the same sweep and overrides the LLM's
    `no_original_answer_leakage` if any literal leak is found.
- **LLM hardening**: provider checks Azure `status` / `incomplete_details`;
  on `max_output_tokens` truncation it auto-retries once with doubled budget
  (capped at 32k); any other incomplete (`content_filter`, `failed`,
  unparseable JSON) raises `ProviderIncomplete(reason=...)` which steps map
  to distinct `failed:llm_<reason>` labels.
  ([src/perturb/providers/azure_openai.py](../src/perturb/providers/azure_openai.py))

---

## Data layout

```
data/
  raw/        garage_train.jsonl              (perturb fetch)
  exp/        exp-300.jsonl                   (perturb exp build)
              exp-300.manifest.json
  runs/<id>/  manifest.json
              01_filter.jsonl
              02_perturb.jsonl
              03_validate.jsonl
  traces/<id>/perturb.jsonl                   (one trace event per LLM call)
              validate.jsonl
  cache/                                       (HF + future caches)
reports/                                       (any analysis output you generate)
```

`.gitignore` excludes `data/raw/`, `data/runs/`, `data/traces/`, `data/cache/`,
and `reports/*.md|csv`. **`data/exp/` is intentionally tracked** so your frozen
curated set is reproducible across machines. Specific completed experimental
runs are `git add -f`'d when worth preserving (see the historical experiment notes in `archive/research-notes/experiments.md`).

---

## CoreRecord — the contract between steps

Defined in [src/perturb/schemas.py](../src/perturb/schemas.py). Populated
progressively:

| Step | Fields populated |
|---|---|
| `filter` | `core_id`, `garage_sample_id`, `question`, `answer_generate`, `all_grounding_original`, `answer_containing_passage_ids`, GaRAGe metadata |
| `perturb` | `atomic_claim_original/perturbed`, `original_value`, `perturbed_value`, `perturbation_type/subtype`, `plausibility`, `deducibility_note`, `sent_passage_ids`, `doc_modifications`, `backstop_modified_passage_ids`, `modified_passage_ids`, `all_grounding_perturbed` |
| `validate` | `validation` (5 booleans + plausibility + `rejection_reasons`) |

Every step also writes its name into `pipeline_state[step]` and (for LLM steps)
auto-stamps `generators[step_name]` with `StepProvenance(provider, model,
run_id, completed_at)`. Last-writer-wins on re-runs / cross-model overlap;
full per-call history lives in `data/traces/<run_id>/<step>.jsonl`. The
`generators` dict is what lets you mix records from different perturber runs
in one analysis without joining manifests.

---

## Providers

[src/perturb/providers/](../src/perturb/providers/) — name-keyed registry.
Each adapter implements `LLMProvider.complete_json` returning a parsed JSON
object. Built-in:

| name | code | wire shape | env vars |
|---|---|---|---|
| `azure-gpt` | [azure_openai.py](../src/perturb/providers/azure_openai.py) | Azure OpenAI Responses API; 4xx body captured, max_output_tokens retry once (cap 32K) | `AZURE_GPT_ENDPOINT`, `AZURE_GPT_API_KEY`, `AZURE_GPT_API_VERSION`, `AZURE_GPT_MODEL` |
| `grok` | [grok.py](../src/perturb/providers/grok.py) | Azure AI Foundry chat completions; reasoning_effort=medium, 32K floor, single-shot on length, 600s timeout | `AZURE_GROK_ENDPOINT`, `AZURE_GROK_API_KEY`, `AZURE_GROK_MODEL` |
| `gemini` | [gemini.py](../src/perturb/providers/gemini.py) | google-genai SDK (vertex_express OR vertex full ADC); ThinkingConfig=HIGH, safety_settings=OFF, 32K floor | `GOOGLE_CLOUD_API_KEY` *or* `GEMINI_API_KEY` (Vertex Express) *or* `GOOGLE_CLOUD_PROJECT` (Vertex full); `GEMINI_MODEL` |
| `kimi` | [kimi.py](../src/perturb/providers/kimi.py) | Azure AI Foundry chat completions; reasoning_effort=medium, 32K floor, single-shot | `AZURE_KIMI_ENDPOINT`, `AZURE_KIMI_API_KEY`, `AZURE_KIMI_MODEL` |

All providers share a `ProviderIncomplete(reason=...)` exception class so steps
emit precise `failed:llm_<reason>` labels (`http_400`, `content_filter`,
`max_output_tokens`, `unparseable`, `safety`, `sdk_error`, etc.). The `azure-gpt`
adapter accepts both bare endpoints and pre-built `/openai/responses?...` URLs.

Add a new provider in three lines:

```python
# src/perturb/providers/myprovider.py
from . import register
class MyProvider:
    name = "my"
    model = "..."
    def complete_json(self, *, system, user, schema_hint, temperature, max_tokens): ...
register("my", lambda: MyProvider(...))
```

Then import it from [providers/\_\_init\_\_.py](../src/perturb/providers/__init__.py).

---

## Adding a new pipeline step

1. Subclass `Step` in `src/perturb/steps/<name>.py`
   ([base.py](../src/perturb/steps/base.py)).
2. Append the name to `STEP_ORDER` in [run.py](../src/perturb/run.py).
3. Register the class in [steps/\_\_init\_\_.py](../src/perturb/steps/__init__.py).

The CLI auto-generates a `perturb <name>` subcommand, the pipeline runs it
in order, and the viewer surfaces it (record merge walks `STEP_ORDER`; trace
tab reads `data/traces/<run>/<name>.jsonl`).

---

## Viewer

`perturb viewer` boots a FastAPI app
([viewer/app.py](../src/perturb/viewer/app.py)) that serves a single-page UI
([viewer/templates/index.html](../src/perturb/viewer/templates/index.html) +
[viewer/static/app.js](../src/perturb/viewer/static/app.js)). Backed by:

- [viewer/data.py](../src/perturb/viewer/data.py) merges step outputs into one
  record per `core_id` (latest step wins), groups trace events by `core_id`,
  produces side-by-side passage diffs.
- [viewer/watcher.py](../src/perturb/viewer/watcher.py) uses `watchfiles` to
  publish FS-change events to all subscribers; the UI consumes them via SSE
  at `/api/events` and debounces refetches at 250ms.

Tabs per record: **Overview** (claim, perturbation summary, pipeline_state) ·
**Original / Perturbed** (passage cards with span highlights) · **Diff**
(side-by-side per passage) · **Modifications** (one per `doc_modifications`
entry, expandable rewritten text) · **Validation** (5 gates + reasons) ·
**Traces** (one card per LLM call, collapsible system / user / raw / parsed).

---

## Known limitations / next moves

- **Single-shot validation.** No feedback loop today. Natural next addition:
  on `failed:validation`, re-prompt `perturb` with `rejection_reasons`
  injected, then re-validate. Would lift the ~20–40% first-shot yield.
- **Sequential LLM calls.** No concurrency. A `--workers N` flag using
  `ThreadPoolExecutor` would cut wall-time roughly by N (Azure quota
  permitting).
- **Validator sees only modified passages.** It can't catch a passage the
  perturber *missed* sending. The deterministic backstop covers literal
  leakage, not paraphrased mentions.
- **Generator, label-evaluator, and judge steps are implemented.** See
  `src/perturb/steps/generate.py`, `label_eval.py`, and `judge.py`.
  The saved production matrix and its run inventory are documented in
  [paper/REPRODUCIBILITY.md](../paper/REPRODUCIBILITY.md).

---

## Quick reference

```bash
# data
perturb fetch                                  # pull GaRAGe
perturb exp build exp-300 --source ... --n 300 # freeze curated set
perturb exp ls / show <name>

# runs
perturb runs new --name <label>                # mint run id
perturb runs ls / show <id>

# pipeline (any provider: azure-gpt | grok | gemini | kimi)
perturb pipeline --run $RUN --source ... --model <provider> [--take N --offset M] [--resume]
perturb filter   --run $RUN --source ... [--take N --offset M]
perturb perturb  --run $RUN --model <provider> [--types ...] [--resume]
perturb validate --run $RUN --model <provider> [--resume]

# inspect
perturb stats    $RUN [--detailed]
perturb inspect  $RUN --step <name> [--core-id X | --index N]
perturb traces   $RUN --step <name> --tail 5
perturb viewer                                  # http://127.0.0.1:7437

# providers
perturb models
```
