# Camera-ready triage: Eval-Pair Matrix

Updated 12 September 2026 after the authors selected the revision scope. No new model calls or human annotations have been made. The decisions below supersede the original triage recommendations retained later in this document.

## Author-approved scope and progress

Work proceeds one item at a time. Show exact old/new wording in an in-context review PDF (orange old text, arrow, yellow proposed text) before applying manuscript changes. Items 1, 2, 4, 6 and 7 are approved and applied. Changes, once approved, should be integrated into the existing prose without revision-history language in the paper. The later explicit request authorizes a minimal abstract endpoint qualifier and the eight reporting/limitation corrections recorded in `paper/review/targeted_corrections.json`; avoid broader rewrites.

| Item | Decision | Status |
|---|---|---|
| 1. Constrain central claims to the measured contrast | Accepted | Four minimal sentence-level replacements applied; abstract unchanged; clean PDF rebuilt and PubCheck All Clear |
| 2. Correct audit interpretation; preserve the −4.3 pp result | Accepted | Eight reviewed source replacements applied; clean PDF rebuilt and PubCheck All Clear |
| 3. Exact label-pipeline reporting and new sensitivity analysis | Reporting now authorized; new analyses skipped | Minimal count, label-rule, and fallback clarifications applied |
| 4. Prominence of heterogeneous endpoint results | Accepted | Three reviewed replacements applied; clean PDF rebuilt and PubCheck All Clear |
| 5. Independent second human audit | Skip | Out of scope |
| 6. Practical computational cost | Accepted | Both reviewed additions applied; clean PDF rebuilt and PubCheck All Clear |
| 7. Smaller/local-model discussion | Accepted | Rephrased as untested generalization beyond three proprietary endpoints, with protocol controls |
| 8. Additional model-version/reference consistency work | Skip | No further work; prior reference corrections remain |
| 9. Artifact consistency and final production checks | Accepted | Local release pass complete: documentation, portable cost ledger, reproduced analyses, two PDFs and source/reproducibility packages; external repository access and submission remain |

**Item 1 status:** the authors approved the four minimal replacements in the introduction's result summary, empirical contribution, related-work pairing description, and recall-results paragraph. All four yellow replacements are now in the manuscript, without orange text or review markup. An exact comparison against the immediate pre-acceptance snapshot confirms that these are the only scientific source changes. The abstract, discussion, conclusion, existing limitations, headings, captions, and appendix remain unchanged. The earlier broad proposal was rejected and is not part of the manuscript.

**Item 2 status:** all eight reviewed replacements are approved and applied. The clean manuscript preserves the −4.3 pp result, confidence interval, and audit judgments; it now distinguishes the audit's measurement lesson from the unresolved cause of the matching-judge gap, describes the saved audit queue and coverage accurately, and removes unsupported rule-of-three bounds. The abstract and result tables are unchanged. Exact source comparison confirms only the approved replacements were applied. The earlier audit review PDF is retained as an accepted historical proposal.

**Item 4 status:** all three reviewed replacements are approved and applied. The results paragraph now reports GPT −3.8 pp, Grok −3.7 pp and Gemini +6.0 pp recall contrasts as exploratory, with uncorrected intervals; the conclusion reflects their differing directions. The introduction and conclusion no longer describe the avoided-claim gap as the only robust paired effect. No estimates, tables, abstract text, or appendix text changed in this step. The earlier heterogeneity review is retained as an accepted historical proposal.

**Item 6 status:** both reviewed cost additions are approved and applied: the short discussion paragraph and the appendix subsection/table. The paper reports quadratic judging-call scaling, frozen-answer reuse, and recorded usage for the nine production judge runs. `paper/audit/judge_cost.py` reproduces 2,688 logged calls, 2,683 verdicts, five failures, 5,626,958 input tokens, 308,181 output tokens, and 4.883 hours of summed call time. The appendix defines the scope and incomplete token/retry accounting. The earlier 4.885-hour triage approximation summed rounded run values; summing raw milliseconds gives 4.883 hours. Exact source comparison confirms only the two approved additions were applied. Main text and the artifact statement still fit within eight pages; the PDF is now 16 pages because of the appendix addition. The abstract and existing results are unchanged. The cost review PDF is retained as an accepted historical proposal.

**Item 7 status:** the initial 26-word capability sentence was accepted, then explicitly revised at the authors' request to state the limitation: results cover three large proprietary endpoints and generalization to smaller local models is untested. The protocol controls remain. The same targeted pass applies the eight minimal reporting/limitation corrections in `paper/review/targeted_corrections.json`; no new analyses were added.

**Item 9 status:** the root README now identifies the final 3provider_300 pool and completed matrix. `paper/REPRODUCIBILITY.md` gives canonical saved-data analysis commands, expected outputs, and package contents. A usage-only ledger makes cost accounting portable and produces a byte-identical report to the raw traces. Paired/behavior reports, existing sensitivity values/table, and the audit queue were independently reproduced in a scratch tree. The clean PDF and complete original-to-final comparison are built and checked. Source and reproducibility ZIPs are prepared locally. The GitHub URL still returns 404 without authentication; repository publication and portal upload have not been performed. See `paper/CAMERA_READY_STATUS.md` for final evidence and external steps.

**Already completed:** unmodified official ACL style, final-mode wrapper, supplied author names/affiliation/emails, abstract length and layout adjustments, verification of all 24 reference titles and author lists, and an eight-page main body in the current 16-page PDF. The artifact URL now points to `https://github.com/selvamsriram/eval-pair-matrix`. An unauthenticated GitHub request returned HTTP 404 on September 12; public accessibility remains unresolved. Changing repository visibility is not part of this link-edit pass. See `paper/CAMERA_READY_STATUS.md` for production checks.

**Approved approach:** retain the methodological contribution and existing experiment; narrow the empirical claims and audit interpretation, make endpoint heterogeneity clear, add computational-cost reporting and an ultra-minimal local-model discussion, and complete camera-ready packaging. Minimal label-pipeline/count reporting corrections were subsequently authorized and applied; new sensitivity analyses, independent annotation, and additional provenance work remain declined.

The official [GroundLM camera-ready instructions](https://groundlm.github.io/grouplm_emnlp2026/camera-ready.html) give a September 12, 2026 AoE deadline and require official ACL formatting, author/affiliation details, accurate references, and PDF validation. They do not establish an extra main-text page allowance. Plan around the accepted eight-page main-text budget. This is a regular Track 1 archival paper, not a shared-task system paper.

## What was inspected

- The supplied OpenReview PDF: acceptance decision, area-chair meta-review, Reviewer QVWs's positive review, and Reviewer LkgT's negative review.
- The 15-page `paper/acl_submission.pdf`, its complete main text and appendix sources, bibliography, and rendered pages. This PDF matches the supplied `Submitted_68_Eval_Pair_Matrix_Answer_Pai.pdf` byte for byte (SHA-256 `f481908bb3a734f038605f655a4d014a2bd57a35a76bb67fb264a39d39373dac`). `archive/paper_old_for_records/` is historical. The new reviewable output is `output/pdf/eval-pair-matrix-camera-ready.pdf`.
- `README.md`, `PROPOSAL.md`, dataset manifests, the pipeline, prompts, schemas, provider adapters, labeling and judging code, raw generation/label/judge files, traces, paired-analysis code, human-review queue/progress/codebook, and figure generation.
- Independent read-only count and point-estimate checks against raw JSONL, followed by cluster-bootstrap checks on the saved paired verdict table, using the paper's 10,000 replicates and seed 20260627.

## What we already have

| Asset | Verified state | What it enables today |
|---|---|---|
| Primary manuscript | Shared `main_body.tex`, `appendix_content.tex`, and `references.tex`; dedicated final ACL wrapper in `camera_ready.tex` | Focused revisions without reconstructing the paper |
| Frozen benchmark | 300 core records; 275 pass all five gates; selected perturbers 83 GPT / 92 Grok / 125 Gemini | Reproducible existing-data analyses |
| Generation and labels | 900 output slots, 896 nonempty answers; 897 populated evaluation fields include four synthetic failure labels; 893 nonempty answers have LLM labels and three lack them | Accurate count funnel and fallback-label sensitivity |
| Judge matrix | 2,683 verdicts over 896 distinct nonempty answers; 894 full-set paired answers | No need to rerun the matrix |
| Validated paired set | 819 answers; 456 adoption-positive and 363 adoption-negative; 816 have all three verdicts | Explicit denominators and complete-triplet sensitivity |
| Audit | 88 reviewed verdict cases out of 153 sampled; 79 distinct answers from 70 records; apparent-FP subset is 25 answers from 22 records | Existing audit evidence and material for independent re-review |
| Provenance | Logged model IDs are `gpt-5.4`, `grok-4.3`, and `gemini-3.5-flash`; GPT labeling uses `gpt-5.4` | Model-role/provenance table; the `gen-gpt55-300` directory name should not determine the reported model |
| Cost traces | Nine production judge runs have call counts, token usage, latency, and failures | Measured cost/scaling note without new inference |

The final release pass corrected the README's earlier 100/100/100 pool and planned-track descriptions. `paper/REPRODUCIBILITY.md` and `paper/audit/README.md` identify canonical numerical outputs and distinguish historical narrative summaries from the accepted interpretation.

## Original review-by-review triage (superseded by author decisions above)

Effort estimates are rough implementation and author-review time; some items overlap. P0 means necessary for the recommended submission; P1 means high-value and feasible; conditional items depend on people/time.

| Priority | Comment and source | Decision | Concrete change | Effort |
|---|---|---|---|---|
| P0 | Single endpoint per provider cannot separate model identity, provider, and style; null result overgeneralized. AC + LkgT | Address interpretation fully; acknowledge unresolved experimental limitation | Define a matching-versus-nonmatching endpoint contrast conditional on the tested dataset, prompts, labels, and endpoints. Revise abstract, introduction, contribution bullets, related-work identification claim, discussion, and conclusion. State that answer pairing holds the answer fixed but does not isolate the mechanism of identity-based self-leniency. | 45–75 min |
| P0 | No evidence of absence; small validated sample. LkgT | Address precision and scope; skip dataset expansion | Keep the effect and CI, distinguish aggregate mean from endpoint-specific effects, and state that a CI covering zero is not an equivalence test. Do not add post-hoc power calculations or a margin chosen to make the result equivalent. | Included above |
| P0 | Audit of 25 apparent FPs does not establish that label/task mismatch explains the entire gap. LkgT | Address directly | Describe 22 alternate errors, two label mistakes, one unclear case as findings in the reviewed subset. The audit demonstrates why adoption-negative flags are not synonymous with false alarms; it does not identify the cause of the full matching-judge gap or rule out leniency toward other source errors. | 30–45 min |
| P0 | The one robust effect is explained away and the empirical contribution is thin. LkgT | Address the presentation; do not manufacture another result | Retain the observed −4.3 pp avoided-claim flagging difference as an empirical result with unresolved mechanism. Present the protocol, measured aggregate contrast, endpoint heterogeneity, and audit's measurement lesson as the contribution. Remove claims that the audit turns the flagging difference into evidence against self-leniency. | Included in claims/audit revisions |
| P0 | Adoption/behavior labels come from GPT, one of the evaluated models. AC + LkgT | Partially address with transparency and existing-data sensitivity; keep limitation explicit | Document exact gold derivation and fallback behavior. Add labeled complete-triplet, direct-entailment, and audited-label-issue exclusion sensitivities in one compact appendix table. Shared labels do not automatically remove bias: they determine which answers enter recall and avoided-claim strata. | 45–90 min |
| Conditional, highest-value extension | Single adjudicator, no agreement statistics. AC + LkgT | Do if a second human is available | Independently re-review the 25 apparent-FP answers plus approximately 10–15 existing TP/FN/TN controls; preserve separate ratings, hide previous human decisions and provider identities, then adjudicate disagreements. Report agreement on comparable annotation fields and counts before adjudication. Report kappa only where meaningful; a constant category can make it uninformative or undefined. | 30–60 min preparation; 2–4 human hours; 30–45 min integration |
| P1 | Opposite per-generator effects; exploratory comparisons uncorrected. LkgT | Address with existing results | Explicitly report GPT −3.8 pp, Grok −3.7 pp, Gemini +6.0 pp as heterogeneous descriptive estimates. Retain exploratory/uncorrected labeling. Do not present the aggregate as uniform behavior across endpoints. Additional multiplicity-adjusted inference is optional and unnecessary if no subgroup discovery claims are made. | 15–30 min |
| P1 | Practical cost of the full matrix. QVWs | Fully address | Add a short practitioner paragraph and an appendix table from the production traces: calls, successful verdicts, recorded tokens, aggregate call time, and missing-usage caveats. Explain quadratic judge-call scaling. | 30–60 min |
| P1 | Generalization to smaller/open/local models. QVWs | Fully address the requested discussion; defer experiments | Explain that the protocol can use local generators/judges with the same source inputs and structured outputs; context limits, refusal behavior, format failures, inference budget, and quantization must be controlled/reported. Do not extrapolate the empirical near-zero result to them. | 15–25 min |
| P1 | Check model versions and REFLECT. LkgT | Bibliography verified; finish model provenance | Exact logged IDs are `gpt-5.4`, `grok-4.3`, and `gemini-3.5-flash`. Add a compact provenance note with roles and recorded settings/dates; distinguish configured IDs from immutable backend snapshots. REFLECT's title, authors, arXiv ID and 2026 date match its primary record. All 24 cited titles/author lists were verified; one omitted author in a different reference was restored. | 20–40 min remaining |
| P0 production | Camera-ready preparation and the user's public artifact link | Formatting, authors and link completed; release/QA remain | Refresh the canonical README, synchronize affected tables/figures, confirm public repository access, rebuild and visually inspect the final PDF, and repeat ACL PubCheck after scientific revisions. The supplied URL currently returns 404 without authentication; do not claim public availability has been verified. | 30–60 min remaining |

## Additional corrections found in the repository

These are not requests for a new experiment. They make the paper describe the existing experiment accurately.

1. **Correct “the only robust paired gap.”** Table 3 also reports an overall flagging difference of −2.2 pp with CI [−3.8, −0.6]. Explain its relationship to the adopted/avoided strata, or avoid exclusivity language. Evidence: `paper/main_body.tex:2,22,193,204`.

2. **Describe the actual adoption-label rule.** The manuscript describes deriving gold from `entails_perturbed_claim`, but `_derive_gold` also uses behavior and original-claim entailment. There are four answers / twelve verdicts where the stored gold differs from the perturbed-entailment flag, plus three nonempty answers without an LLM evaluation that use a deterministic fallback. Document the frozen primary rule rather than silently replacing it. Evidence: `src/perturb/steps/judge.py:48–70`, `paper/main_body.tex:155`.

3. **Separate intended outputs, nonempty answers, genuine LLM labels, and synthetic failure labels.** “897 usable outputs” is not the raw-data count of usable answers: it is the count of populated evaluation fields, including four synthetic labels for empty generations. The raw files contain 896 nonempty answers, 893 of which have LLM-produced labels. Evidence: `src/perturb/steps/label_eval.py:143–157`, `paper/main_body.tex:86,150`.

4. **Make missing judge verdicts explicit.** The printed equation assumes two cross judges, while the script accepts at least one. In the validated primary analysis, 819 answers are paired and 816 have complete triplets; three paired answers also lack LLM labels. State the available-judge rule and show a complete, labeled subset. Evidence: `paper/audit/paired_audit.py:313–337`, `paper/main_body.tex:187–191`.

5. **Repair the audit sampling description.** The queue builder samples within strata using a fixed seed and then orders by behavior/cell and case ID. The saved 88 completed cases are not the first 88 entries in that queue; the dashboard permits filtering and selection. Unless there is separate evidence of another randomized review order, replace “first 88 in a shuffled queue” with “88 completed cases from a seed-fixed, stratified queue” and state that completion was partial. Evidence: `paper/audit/build_cell_review_queue.py:199–218`, saved queue/progress, `paper/main_body.tex:246`, `paper/appendix_content.tex:302`.

6. **Report the audit unit correctly.** The 88 observations are judge-verdict cases, not 88 independent questions. They represent 79 answers and 70 records; the 25 apparent-FP cases represent 25 answers and 22 records. Remove population-like rule-of-three claims, or describe them only as hypothetical iid-binomial illustrations that do not establish population bounds for this targeted, partially completed, clustered audit. Evidence: `paper/main_body.tex:286` and the queue/progress files.

7. **Use “primary,” not unsupported “prespecified/confirmatory.”** The repository describes the paired analysis as a revision after examining the original matrix. Without a documented prospective analysis plan, “primary analysis” is the accurate label. Evidence: `paper/main_body.tex:193,203`, `paper/audit/paired_audit.py` and historical audit notes. This does not invalidate estimation; it changes the evidential framing.

8. **Align validation and metric descriptions with their scope.** “Validated” means passing automated gates, not independently human-certified. The validator sees modified passages; the deterministic leakage scan covers all passages but only literal/normalized matches. Also label matrix precision/F1 as agreement with adoption labels, not validated any-error accuracy. Evidence: `src/perturb/steps/validate_step.py`, `paper/main_body.tex:80,181,219`.

## Existing-data sensitivity checks already assessed

These read-only triage calculations support adding a short sensitivity table. They are not new independent gold labels and do not resolve provider confounding. Confidence intervals below resample the 275 validated record IDs with 10,000 replicates, seed 20260627. All effects are percentage points, matching minus nonmatching judges.

| Analysis | Paired answers | Recall delta [95% CI] | Avoided-claim flag delta [95% CI] |
|---|---:|---:|---:|
| Reproduced primary | 819 | −0.55 [−2.72, +1.69] | −4.27 [−6.59, −2.00] |
| LLM-labeled answers with all three verdicts | 813 | −0.55 [−2.73, +1.70] | −4.19 [−6.52, −1.94] |
| Exclude seven answers with audited label mistakes or uncertainty | 812 | −0.66 [−2.79, +1.51] | −4.44 [−6.78, −2.19] |
| Use perturbed-claim entailment directly on LLM-labeled answers | 816 | −0.54 [−2.70, +1.69] | −4.48 [−6.82, −2.19] |

For final integration, make these checks reproducible in a dedicated analysis script and preserve the original primary estimand. Do not combine alternative labeling rules or present targeted-audit exclusions as an unbiased correction of the full dataset. No conclusion should be chosen because a particular sensitivity is favorable.

## Computational-cost addition

The nine production judge trace files contain 2,688 call events: 2,683 successful verdicts and five failed calls. Successful events record **5,626,958 input tokens and 308,181 output tokens**. Summed latency across judge calls is approximately **4.883 hours**; this is aggregate call time, not elapsed end-to-end wall-clock time, since independent runs can overlap.

For N records, G generators, J judges and one answer per generator/record, judging costs N×G×J calls. When G=J=K, it is NK²; a diagonal-only evaluation uses NK, so the full three-model matrix requires three times as many judge calls. On a frozen benchmark, generation and one labeling pass each scale as NK. Benchmark construction/validation is additional and should be reported separately.

These are logged quantities, not an invoice. Failed-call usage and internal retries are not fully itemized, and the Gemini adapter records candidate-output tokens without a separate reasoning-token field. A dollar figure would need a dated pricing schedule or billing record and explicit treatment of these omissions; it is not necessary to satisfy the reviewer's request. Do not label a token-derived estimate as actual money spent.

## What to skip today

| Deferred work | Why | What remains in the paper |
|---|---|---|
| Multiple endpoints within every provider family | Requires expanded generation, judging, labeling, analysis and validation; cannot repair the design just by adding one judge | Explicit identity/provider/style limitation and a concrete future design |
| New open-weight/local-model matrix | Requires adapter/setup work, prompt and context checks, and a comparably crossed experiment | Discussion requested by QVWs; no unsupported performance claims |
| Larger question set or another dataset | New construction, generation and judging chain | Dataset-conditional estimate and current uncertainty |
| Relabel every answer with another LLM or humans | Major workload; a second matrix model is not an independent gold standard merely because it differs from GPT | Exact label provenance, bounded sensitivity checks and residual circularity limitation |
| Broad prevalence audit or completion of all 65 remaining queued cases | Finishing a targeted queue does not by itself make it representative; independent re-review is more valuable today | Targeted mechanism audit with truthful coverage and units |
| Repeated stochastic judge calls, prompt sweeps or a new adoption-only judging task | Changes scope and adds an experiment; useful future work | Single-shot and task-alignment limitations |
| New causal model or post-hoc equivalence claim | Existing data cannot fully separate identity from family/style; fitting more parameters does not create that missing variation | Descriptive paired endpoint contrast, not a mechanism claim |

If no second person is available, retain the single-adjudicator limitation. Another LLM's assessment can be an explicitly labeled auxiliary model audit, but cannot be reported as independent human annotation or human inter-rater agreement.

## Suggested execution order

The numbered order below is the proposed priority order for author review. If an independent human is available, their annotation can start early while the manuscript work proceeds.

1. **Constrain the central claim to what the design measures.** Address the AC and LkgT on endpoint confounding, absence claims, sample size and abstract/conclusion scope. Revise high-visibility paragraphs consistently, including the identification claim in related work. Keep the title, research question, dataset and primary estimates.
2. **Correct the audit interpretation and preserve the observed flagging difference.** Address LkgT on the 25-case audit and the effect being explained away. Report the actual case breakdown, partial stratified sampling, clustered units and single-rater status. Remove population-like rule-of-three claims. Preserve the SEC/FASB example and distinguish a valid illustration from an explanation of the aggregate gap.
3. **Make the measurement pipeline exact and add bounded sensitivities.** Address the AC and LkgT on GPT labels and the audit's label issues. Correct the count funnel, exact gold rule, missing-verdict rule, automated-validation scope and unsupported prospective-analysis language. Make the three already-assessed sensitivities reproducible and add one compact appendix table. Keep the frozen primary analysis and all raw records/human judgments intact.
4. **Give endpoint heterogeneity appropriate prominence.** Address LkgT's inconsistent/uncorrected per-generator results with existing Table 3 and a short discussion. Label subgroup estimates exploratory, explain that the aggregate can obscure different signs, and remove broad uniform-behavior claims. No new significance search.
5. **Conditionally strengthen the human evidence.** Address LkgT's double-annotation request and the AC's limited-human-validation concern if another person can independently re-review the proposed 35–40 cases today. Otherwise retain a candid single-rater limitation; the first four priorities still materially improve the paper. Do not treat this as a completed reviewer request without actual independent ratings.
6. **Add practical computational cost.** Fully answer QVWs with measured judge-call/token totals, aggregate call time, scaling, and a short explanation of how cached answers can be reused. Keep benchmark construction costs separate and avoid an invented dollar bill.
7. **Discuss smaller, locally hosted models.** Fully answer QVWs's requested brief discussion with protocol applicability and concrete context/output/budget controls. Leave empirical generalization unclaimed.
8. **Finish model provenance.** Close LkgT's minor consistency request with logged request IDs and model roles/settings. Bibliographic verification, including REFLECT, is already complete.
9. **Make the linked artifact usable and validate the final production files.** Update the canonical README's stale status/counts and point to frozen inputs and reproduction commands. Resolve public access before making an availability claim, reconcile edited captions/tables, rebuild, inspect every page and repeat PubCheck. Funding/acknowledgment/conflict wording remains dependent on applicable author-supplied information; no declaration should be invented. Leave time for author review and the regular-track upload.

**Scope cap:** targeted paragraph, methods, caption and appendix edits; one compact sensitivity table, one compact cost table and a provenance note. Preserve the overall structure, accepted methodological contribution, existing primary experiment and eight-page main-text budget. No broad literature rewrite, new benchmark or repository refactor.

Allow roughly **4–6 focused hours for the core package including review and production**, depending on how much layout adjustment the added material needs. Independent human review adds roughly 2–4 human hours and can happen alongside the other work. If time is shorter, prioritize accurate claims/methods, the cost and smaller-model paragraphs, and final PDF checks; omit optional new annotation before compromising these essentials.

## Suggested empirical framing

> Across the three tested endpoints on the validated GaRAGe-derived sample, the average matching-versus-nonmatching judge recall contrast was −0.5 percentage points (95% cluster-bootstrap CI [−2.7, +1.7]), with heterogeneous endpoint-specific estimates. This result is conditional on the tested endpoints and automatic adoption labels and does not establish absence of same-model bias. A targeted audit documents that adoption-negative flags can be valid detections of other source errors, limiting their interpretation as false alarms.

Reference check: [REFLECT's primary arXiv record](https://arxiv.org/abs/2605.19196) lists the manuscript's title and authors and a May 18, 2026 submission date. Its 2026 citation is consistent.
