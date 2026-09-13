# Historical experiment notes

Preserved from the pre-cleanup README. Run IDs and paths describe earlier experiments; the final paper uses `data/exp/3provider_300.jsonl`. Commands assume the repository root.

## Historical first production datasets

These earlier runs used three perturbers over disjoint slices of `exp-300`.
The final paper instead uses `3provider_300`, described above. Records carry `generators[step]` so they merge
cleanly into one analysis.

| Slice | Perturber | Run id | Validation pass | Notes |
|---|---|---|---|---|
| `[0:100]` | GPT-5.4 (Azure OpenAI Responses) | `20260530-120201-100q-first` | **31/100** | First production run. Backfilled with `generators` field. Includes 1 `http_400` (Azure content_filter on political prompt). |
| `[100:200]` | Grok 4.3 (Azure AI Foundry) | `20260530-142314-100q-grok` | **57/100** | Cleaner contextual-anchor scrubbing than GPT. |
| `[200:300]` | Gemini 3.5 Flash HIGH (Vertex Express) | `20260530-162330-100q-gemini` | **92/100** | Best quality across all 5 gates. Thinking=HIGH, safety=OFF, 32K token floor. |

The smoke runs that informed each provider's tuning are also committed for
audit: `20260530-140815-10q-grok`, `20260530-161345-10q-gemini-high`.

**Combined dataset for Phase 2 inputs:** `data/exp/exp-300-perturbed.jsonl` —
round-robin interleave of the three runs above. 300 records, perturb-provider
breakdown 100/100/100, any contiguous slice draws ~evenly from each model
(verified: 10/10/10 on any 30-slice, 33/34/33 on any 100-slice). Built via
`perturb exp combine` (above).
