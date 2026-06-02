"""CLI surface: `perturb <subcommand>`.

Design goals:
  - one subcommand per pipeline step (audit-friendly smoke runs)
  - `pipeline` chains them with the same run id
  - `inspect` / `stats` / `runs` for after-the-fact auditing
  - `providers` to see which models are configured
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from . import providers
from .config import PATHS
from .exp import build_balanced_exp, build_exp, combine_exp, exp_path, list_exp
from .fetch import fetch_garage
from .io import read_jsonl
from .run import STEP_ORDER, list_runs, new_run, open_run
from .runner import run_step
from .schemas import CoreRecord

app = typer.Typer(add_completion=False, no_args_is_help=True, help="GaRAGe perturbation pipeline.")
console = Console()


# ---------- fetch ----------


@app.command()
def fetch(
    split: str = typer.Option("train", help="HF dataset split."),
    out: Optional[Path] = typer.Option(None, help="Output JSONL path. Defaults to data/raw/garage_<split>.jsonl."),
    limit: Optional[int] = typer.Option(None, help="Take only the first N rows (smoke runs)."),
):
    """Download GaRAGe from HuggingFace into data/raw/."""
    dest = fetch_garage(split=split, out=out, limit=limit)
    console.print(f"[green]wrote[/green] {dest}")


# ---------- exp (frozen curated datasets) ----------

exp_app = typer.Typer(no_args_is_help=True, help="Frozen curated experimental datasets.")
app.add_typer(exp_app, name="exp")


@exp_app.command("build")
def exp_build_cmd(
    name: str = typer.Argument(..., help="Dataset name, e.g. 'exp-300'."),
    source: Path = typer.Option(..., "--source", "-s", help="Raw GaRAGe JSONL."),
    n: int = typer.Option(300, "--n", help="Target curated size."),
    seed: int = typer.Option(17, "--seed", help="Stratification seed (deterministic)."),
    prefer_cited: bool = typer.Option(True, "--prefer-cited/--no-prefer-cited"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace existing dataset of the same name."),
):
    """Build a frozen curated dataset under data/exp/<name>.jsonl with a manifest sidecar.

    Run once. Future pipelines reference this file via --source and slice with --take/--offset.
    """
    out, manifest = build_exp(
        source=source, name=name, n=n, seed=seed, prefer_cited=prefer_cited, overwrite=overwrite
    )
    console.print(f"[green]wrote[/green] {out}")
    console.print(f"raw_row_count: {manifest['raw_row_count']}")
    console.print(f"passing_gates: {manifest['passing_gates']}")
    console.print(f"selected_n:    {manifest['selected_n']} / {manifest['requested_n']} requested")
    if manifest["selected_n"] < manifest["requested_n"]:
        console.print(
            f"[yellow]warning[/yellow]: requested {manifest['requested_n']} but only "
            f"{manifest['selected_n']} passing rows available. "
            f"Run `perturb fetch` (no --limit) for the full dataset."
        )
    console.print(f"strata realized: {len(manifest['strata_counts'])} buckets")


@exp_app.command("ls")
def exp_ls_cmd():
    """List frozen exp datasets."""
    items = list_exp()
    if not items:
        console.print("(no exp datasets — `perturb exp build <name> --source ...`)")
        return
    t = Table("name", "n", "source", "seed", "created")
    for it in items:
        m = it["manifest"]
        t.add_row(
            it["name"],
            str(it["n"]),
            (m.get("source") or "").rsplit("/", 1)[-1],
            str(m.get("seed", "")),
            _ts(m.get("created_at")),
        )
    console.print(t)


@exp_app.command("combine")
def exp_combine_cmd(
    name: str = typer.Argument(..., help="Output dataset name, e.g. 'exp-300-perturbed'."),
    sources: list[Path] = typer.Option(
        ..., "--from", "-f", help="Source JSONL paths (CoreRecord shape). Repeat for each source."
    ),
    order: str = typer.Option(
        "round-robin", "--order",
        help="round-robin (interleave across sources) | sequential (concat) | shuffle (seeded random).",
    ),
    seed: int = typer.Option(17, "--seed", help="Seed used by --order shuffle."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace existing dataset of the same name."),
):
    """Combine multiple CoreRecord JSONLs into one frozen exp dataset.

    With --order round-robin, any contiguous slice of the output draws evenly
    from each input. Use it to merge perturbation runs across multiple models
    into one dataset where a 100-record slice carries records from all sources.
    """
    out, m = combine_exp(sources=sources, name=name, order=order, seed=seed, overwrite=overwrite)
    console.print(f"[green]wrote[/green] {out}")
    console.print(f"order: [bold]{m['order']}[/bold]   total: [bold]{m['total']}[/bold]")
    t = Table("source", "count")
    for src, n in zip(m["sources"], m["source_counts"]):
        t.add_row(src.rsplit("/", 2)[-2] + "/" + src.rsplit("/", 1)[-1], str(n))
    console.print(t)
    if m["provider_breakdown_perturb"]:
        console.print("\n[bold]perturb provider breakdown[/bold]")
        t = Table("provider", "count")
        for p, n in m["provider_breakdown_perturb"].items():
            t.add_row(p, str(n))
        console.print(t)
    if m["validation_pass_rate"]["total"]:
        pr = m["validation_pass_rate"]
        console.print(f"\nvalidation pass rate: [bold]{pr['passed']}/{pr['total']}[/bold] ({100*pr['passed']/pr['total']:.1f}%)")


@exp_app.command("build-balanced")
def exp_build_balanced_cmd(
    name: str = typer.Argument(..., help="Output dataset name, e.g. '3provider_300'."),
    sources: list[Path] = typer.Option(
        ..., "--from", "-f",
        help="Source JSONL paths (CoreRecord shape from finished validate runs). Repeat per provider.",
    ),
    fill_from: Optional[Path] = typer.Option(
        None, "--fill-from",
        help="Source to use when total chosen < --target. Defaults to the source with the highest validated count.",
    ),
    target: int = typer.Option(300, "--target", help="Target total record count."),
    seed: int = typer.Option(17, "--seed", help="Reproducible tiebreak seed."),
    overwrite: bool = typer.Option(False, "--overwrite"),
):
    """Build a balanced multi-source exp dataset.

    One record per question (core_id). Prefer validated records. Balance
    primarily by provider (equal-as-possible up to each provider's capacity),
    secondarily by perturbation_type. Gap-fill from --fill-from if total
    falls short of --target after the validated pass.
    """
    out, m = build_balanced_exp(
        sources=sources, fill_source=fill_from, name=name,
        target=target, seed=seed, overwrite=overwrite,
    )
    console.print(f"[green]wrote[/green] {out}")
    console.print(f"actual: [bold]{m['actual_total']}[/bold] / target {m['target_total']}    "
                  f"(validated_chosen={m['validated_chosen']}, gap_filled={m['gap_filled']})")

    t = Table("provider", "capacity", "target", "actual")
    for p in sorted(set(list(m["provider_max_capacity"].keys()) + list(m["provider_actuals"].keys()))):
        t.add_row(
            p,
            str(m["provider_max_capacity"].get(p, "-")),
            str(m["provider_targets"].get(p, "-")),
            str(m["provider_actuals"].get(p, 0)),
        )
    console.print(t)

    console.print(f"\nsingle-validator questions: {m['single_validator_questions']}")
    console.print(f"multi-validator questions:  {m['multi_validator_questions']}")
    console.print(f"excluded (no perturbation):  {m['excluded_questions_count']}")

    console.print("\n[bold]type distribution per provider[/bold]")
    # collect all types
    all_types = set()
    for p, d in m["type_distribution_per_provider"].items():
        all_types.update(d.keys())
    t = Table("type", *m["type_distribution_per_provider"].keys(), "total")
    for ty in sorted(all_types):
        row = [ty]
        total = 0
        for p in m["type_distribution_per_provider"]:
            v = m["type_distribution_per_provider"][p].get(ty, 0)
            row.append(str(v))
            total += v
        row.append(str(total))
        t.add_row(*row)
    console.print(t)


@exp_app.command("show")
def exp_show_cmd(name: str = typer.Argument(...)):
    """Print the manifest for a built exp dataset."""
    p = exp_path(name)
    if not p.exists():
        console.print(f"[red]not found[/red]: {p}")
        raise typer.Exit(1)
    from .exp import manifest_path as _mp
    mp = _mp(name)
    if not mp.exists():
        console.print("(no manifest)")
        return
    console.print_json(mp.read_text())


def _ts(epoch: int | float | None) -> str:
    if not epoch:
        return ""
    import time as _t
    return _t.strftime("%Y-%m-%d %H:%M", _t.localtime(epoch))


# ---------- runs ----------

runs_app = typer.Typer(no_args_is_help=True, help="Manage run directories.")
app.add_typer(runs_app, name="runs")


@runs_app.command("new")
def runs_new(name: Optional[str] = typer.Option(None, help="Human-readable suffix, e.g. smoke-200.")):
    """Create a new run directory under data/runs/."""
    run = new_run(name=name)
    console.print(f"[green]created[/green] {run.dir}")
    console.print(f"run_id: [bold]{run.run_id}[/bold]")


@runs_app.command("ls")
def runs_ls():
    """List existing runs newest first."""
    runs = list_runs()
    if not runs:
        console.print("(no runs yet)")
        return
    table = Table("run_id", "steps_completed", "dir")
    for r in runs:
        m = r.read_manifest()
        steps_done = [s for s in STEP_ORDER if f"step_{s}" in m]
        table.add_row(r.run_id, ",".join(steps_done) or "-", str(r.dir))
    console.print(table)


@runs_app.command("show")
def runs_show(run_id: str):
    """Print a run's manifest."""
    run = open_run(run_id)
    console.print_json(json.dumps(run.read_manifest()))


# ---------- providers ----------


@app.command()
def models():
    """List registered model providers and whether they're configured."""
    table = Table("name", "status", "model")
    for name in providers.available():
        try:
            p = providers.get(name)
            table.add_row(name, "[green]ready[/green]", p.model)
        except Exception as exc:  # noqa: BLE001
            table.add_row(name, f"[yellow]missing config[/yellow]", str(exc).split(":", 1)[0])
    console.print(table)


# ---------- pipeline steps ----------


def _step_command(step_name: str):
    """Builds a Typer command that runs one pipeline step."""

    def _cmd(
        run_id: str = typer.Option(..., "--run", "-r", help="Run id from `perturb runs new`."),
        source: Optional[Path] = typer.Option(
            None, "--source", "-s", help="Input JSONL. Defaults to the previous step's output."
        ),
        model: Optional[str] = typer.Option(None, "--model", "-m", help="Provider name (see `perturb models`)."),
        limit: Optional[int] = typer.Option(None, "--limit", help="Process at most N records."),
        # Step-specific knobs (kept flat for CLI ergonomics)
        n: Optional[int] = typer.Option(None, "--n", help="(filter, build-from-raw mode) target sampled size."),
        seed: int = typer.Option(17, "--seed", help="(filter) sampling seed."),
        prefer_cited: bool = typer.Option(True, "--prefer-cited/--no-prefer-cited", help="(filter) prefer examples with at least one cited answer passage."),
        take: Optional[int] = typer.Option(None, "--take", help="(filter) take only N records from the slice. Used to dip into a frozen exp dataset."),
        offset: int = typer.Option(0, "--offset", help="(filter) skip the first M records before taking. Combine with --take for non-overlapping slices."),
        paraphrase: bool = typer.Option(True, "--paraphrase/--no-paraphrase", help="(mentions) run the LLM paraphrase pass."),
        types: Optional[str] = typer.Option(None, "--types", help="(perturb) comma-separated allowed perturbation types."),
        generators: Optional[str] = typer.Option(None, "--generators", help="(generate) comma-separated provider names to run as generators, e.g. 'azure-gpt,gemini,grok'. Each generates one answer per record per mode."),
        modes: Optional[str] = typer.Option(None, "--modes", help="(generate) comma-separated modes from {rag_perturbed, rag_original, closed_book}. Default: rag_perturbed."),
        judges: Optional[str] = typer.Option(None, "--judges", help="(judge) comma-separated provider names to use as judges, e.g. 'azure-gpt,gemini,grok'. Each judges every generator output independently."),
        resume: bool = typer.Option(False, "--resume", help="If output already exists, skip records by core_id already in it and append the rest. Use to recover from a crashed run."),
    ):
        run = open_run(run_id)
        options: dict = {
            "limit": limit,
            "n": n if n is not None else 200,
            "seed": seed,
            "prefer_cited": prefer_cited,
            "take": take,
            "offset": offset,
            "paraphrase": paraphrase,
            "types": types,
            "generators": generators,
            "modes": modes,
            "judges": judges,
            "_runner_model": model,  # generate / judge fall back to this if --generators / --judges absent
        }

        # Apply --limit by chopping the source upstream when needed.
        effective_source = source
        if limit is not None and step_name != "filter":
            effective_source = _limited_copy(source or run.input_path_for(step_name), limit, run.dir)

        out_path, statuses = _run_step_with_progress(
            run=run,
            step_name=step_name,
            source=effective_source,
            model=model,
            options=options,
            resume=resume,
        )
        console.print(f"[green]ok[/green] step={step_name} → {out_path}")
        _print_status_counter(statuses)

    _cmd.__name__ = f"step_{step_name}"
    _cmd.__doc__ = f"Run the `{step_name}` step."
    return _cmd


for _step in STEP_ORDER:
    app.command(_step)(_step_command(_step))


def _limited_copy(source: Path, limit: int, run_dir: Path) -> Path:
    """Materialize a head-limited copy of `source` so the step only sees N records."""
    if not source.exists():
        raise FileNotFoundError(f"Input not found: {source}")
    dst = run_dir / f"_limit_{limit}_{source.name}"
    with source.open("rb") as fin, dst.open("wb") as fout:
        for i, line in enumerate(fin):
            if i >= limit:
                break
            fout.write(line)
    return dst


def _count_lines(path: Path | None) -> int | None:
    if path is None or not path.exists():
        return None
    with path.open("rb") as f:
        return sum(1 for line in f if line.strip())


def _run_step_with_progress(
    *,
    run,
    step_name: str,
    source: Path | None,
    model: str | None,
    options: dict,
    resume: bool = False,
):
    """Run a step under a live Progress bar. Returns (out_path, statuses)."""
    effective_source = source if source is not None else run.input_path_for(step_name)
    # filter consumes all input before emitting → bar useless; use spinner.
    total_hint = _count_lines(effective_source) if step_name != "filter" else None
    columns = [
        TextColumn("[bold cyan]{task.description}"),
        SpinnerColumn() if total_hint is None else BarColumn(bar_width=28),
        TextColumn("{task.completed:>3} records") if total_hint is None else MofNCompleteColumn(),
        TextColumn("·"),
        TextColumn("{task.fields[stats]}"),
        TimeElapsedColumn(),
    ]
    with Progress(*columns, console=console, transient=False) as progress:
        task = progress.add_task(step_name, total=total_hint, stats="")

        def cb(_payload, statuses: Counter):
            ok = statuses.get("ok", 0)
            fail = sum(v for k, v in statuses.items() if k.startswith("failed"))
            skip = sum(v for k, v in statuses.items() if k.startswith("skipped"))
            progress.update(
                task,
                advance=1,
                stats=f"[green]ok={ok}[/green] [red]fail={fail}[/red] [yellow]skip={skip}[/yellow]",
            )

        return run_step(
            run=run,
            step_name=step_name,
            source=source,
            model=model,
            options=options,
            progress_cb=cb,
            resume=resume,
        )


def _print_status_counter(statuses: Counter) -> None:
    if not statuses:
        return
    table = Table("status", "count")
    for k, v in statuses.most_common():
        table.add_row(str(k), str(v))
    console.print(table)


# ---------- pipeline (chain) ----------


@app.command()
def pipeline(
    run_id: str = typer.Option(..., "--run", "-r"),
    source: Path = typer.Option(..., "--source", "-s", help="Source JSONL. Raw GaRAGe for build-from-raw mode, or a frozen exp file (data/exp/<name>.jsonl) for slicing."),
    model: str = typer.Option(..., "--model", "-m"),
    n: int = typer.Option(50, "--n", help="(filter, build-from-raw mode) target sampled size."),
    seed: int = typer.Option(17, "--seed"),
    take: Optional[int] = typer.Option(None, "--take", help="(filter, exp mode) take only N records from the slice."),
    offset: int = typer.Option(0, "--offset", help="(filter, exp mode) skip the first M records before taking."),
    types: Optional[str] = typer.Option(None, "--types"),
    stop_after: Optional[str] = typer.Option(None, "--stop-after", help=f"Stop after this step. One of: {','.join(STEP_ORDER)}."),
    resume: bool = typer.Option(False, "--resume", help="For each step, if its output already exists, skip records already there and append the rest. Use to recover from a crashed pipeline."),
):
    """Run the full pipeline (filter → perturb → validate) on one run id.

    Two modes:
      build-from-raw  --source data/raw/garage_train.jsonl --n 100
      exp slice       --source data/exp/exp-300.jsonl --take 100 --offset 0
    """
    run = open_run(run_id)
    last_out: Optional[Path] = None
    for step_name in STEP_ORDER:
        opts: dict = {
            "n": n, "seed": seed, "prefer_cited": True,
            "take": take, "offset": offset,
            "paraphrase": True, "types": types,
        }
        step_source = source if step_name == "filter" else last_out
        out_path, statuses = _run_step_with_progress(
            run=run, step_name=step_name, source=step_source, model=model, options=opts, resume=resume
        )
        console.print(f"[bold green]✓[/bold green] {step_name} → {out_path}")
        _print_status_counter(statuses)
        last_out = out_path
        if stop_after == step_name:
            break


# ---------- audit helpers ----------


@app.command()
def inspect(
    run_id: str = typer.Argument(...),
    step: str = typer.Option(..., "--step", help=f"One of: {','.join(STEP_ORDER)}."),
    core_id: Optional[str] = typer.Option(None, "--core-id", help="Filter to a single record."),
    index: Optional[int] = typer.Option(None, "--index", help="Zero-based record index instead of core_id."),
):
    """Pretty-print one record from a step's output."""
    run = open_run(run_id)
    path = run.step_path(step)
    if not path.exists():
        console.print(f"[red]missing[/red] {path}")
        raise typer.Exit(1)
    for i, raw in enumerate(read_jsonl(path)):
        if core_id is not None and raw.get("core_id") != core_id:
            continue
        if index is not None and i != index:
            continue
        console.print_json(json.dumps(raw))
        return
    console.print("[yellow]no match[/yellow]")


@app.command()
def stats(
    run_id: str = typer.Argument(...),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Per-gate, per-type, plausibility, and rejection-reason breakdowns."),
):
    """Per-step counts and validation pass rate."""
    run = open_run(run_id)
    table = Table("step", "records", "ok", "failed", "skipped")
    for step_name in STEP_ORDER:
        path = run.step_path(step_name)
        if not path.exists():
            continue
        n = ok = fail = skip = 0
        for raw in read_jsonl(path):
            n += 1
            s = (raw.get("pipeline_state") or {}).get(step_name, "")
            if s == "ok":
                ok += 1
            elif s.startswith("failed"):
                fail += 1
            elif s.startswith("skipped"):
                skip += 1
        table.add_row(step_name, str(n), str(ok), str(fail), str(skip))
    console.print(table)

    val_path = run.step_path("validate")
    if val_path.exists():
        passes = 0
        total = 0
        for raw in read_jsonl(val_path):
            total += 1
            try:
                rec = CoreRecord.model_validate(raw)
                if rec.validation.passes:
                    passes += 1
            except Exception:  # noqa: BLE001
                continue
        if total:
            pct = 100 * passes / total
            console.print(f"validation pass rate: [bold]{passes}/{total}[/bold] ({pct:.1f}%)")

    if detailed:
        _detailed_stats(run)


def _detailed_stats(run) -> None:
    from collections import Counter as _C

    perturb_path = run.step_path("perturb")
    validate_path = run.step_path("validate")

    # ---- Perturbation type + plausibility distribution (from latest stage that has them) ----
    src = validate_path if validate_path.exists() else perturb_path
    if not (src and src.exists()):
        return

    type_counts: _C = _C()
    sub_counts: _C = _C()
    plaus_counts: _C = _C()
    for raw in read_jsonl(src):
        if raw.get("perturbation_type"):
            type_counts[raw["perturbation_type"]] += 1
        if raw.get("perturbation_subtype"):
            sub_counts[raw["perturbation_subtype"]] += 1
        if raw.get("plausibility"):
            plaus_counts[raw["plausibility"]] += 1

    if type_counts:
        console.print("\n[bold]perturbation types[/bold]")
        t = Table("type", "count")
        for k, v in type_counts.most_common():
            t.add_row(k, str(v))
        console.print(t)

    if plaus_counts:
        console.print("\n[bold]plausibility (perturber's own rating)[/bold]")
        t = Table("level", "count")
        for k in ("high", "medium", "low"):
            if plaus_counts.get(k):
                t.add_row(k, str(plaus_counts[k]))
        console.print(t)

    # ---- Per-gate pass/fail across validated records ----
    if validate_path.exists():
        gate_names = (
            "type_valid",
            "answer_causal",
            "global_context_consistent",
            "no_original_answer_leakage",
            "original_contradicts_perturbed",
        )
        gate_pass = {g: 0 for g in gate_names}
        gate_fail = {g: 0 for g in gate_names}
        gate_unset = {g: 0 for g in gate_names}
        any_validated = 0
        for raw in read_jsonl(validate_path):
            v = raw.get("validation") or {}
            if all(v.get(g) is None for g in gate_names):
                continue  # not validated (skipped)
            any_validated += 1
            for g in gate_names:
                val = v.get(g)
                if val is True:
                    gate_pass[g] += 1
                elif val is False:
                    gate_fail[g] += 1
                else:
                    gate_unset[g] += 1

        if any_validated:
            console.print(f"\n[bold]per-gate breakdown[/bold]  (over {any_validated} validated records)")
            t = Table("gate", "pass", "fail", "pass %")
            for g in gate_names:
                p, f = gate_pass[g], gate_fail[g]
                pct = 100 * p / (p + f) if (p + f) else 0.0
                t.add_row(g, str(p), str(f), f"{pct:.0f}%")
            console.print(t)

        # ---- Rejection-reason clustering (prefix bucket) ----
        reason_buckets: _C = _C()
        for raw in read_jsonl(validate_path):
            reasons = (raw.get("validation") or {}).get("rejection_reasons") or []
            for r in reasons:
                bucket = _bucket_reason(str(r))
                reason_buckets[bucket] += 1
        if reason_buckets:
            console.print("\n[bold]rejection-reason clusters[/bold]  (top 10)")
            t = Table("cluster", "count")
            for k, v in reason_buckets.most_common(10):
                t.add_row(k, str(v))
            console.print(t)


_REASON_KEYWORDS = [
    ("contextual anchors", "contextual anchor"),
    ("contextual anchors", "anchors"),
    ("leakage (paraphrase)", "still contains"),
    ("leakage (paraphrase)", "still appears"),
    ("leakage (paraphrase)", "leaks"),
    ("leakage (deterministic)", "deterministic_leakage"),
    ("not answer-causal", "not materially"),
    ("not answer-causal", "does not change"),
    ("not answer-causal", "would not change"),
    ("inconsistent context", "globally consistent is false"),
    ("inconsistent context", "still support"),
    ("implausible perturbation", "implausible"),
    ("implausible perturbation", "conflicts with real-world"),
    ("type mismatch", "type_valid is false"),
    ("type mismatch", "grammar"),
]


def _bucket_reason(s: str) -> str:
    low = s.lower()
    for label, kw in _REASON_KEYWORDS:
        if kw in low:
            return label
    return "other"


@app.command()
def traces(
    run_id: str = typer.Argument(...),
    step: str = typer.Option(..., "--step"),
    tail: int = typer.Option(5, "--tail", help="Show the last N trace events."),
):
    """Show the last N LLM trace events for a step (for smoke audits)."""
    run = open_run(run_id)
    path = run.trace_path(step)
    if not path.exists():
        console.print(f"[red]no trace file[/red] {path}")
        raise typer.Exit(1)
    events = list(read_jsonl(path))
    for e in events[-tail:]:
        console.print(f"[cyan]{e.get('event_id', '?')[:8]}[/cyan] "
                      f"core={e.get('core_id')} model={e.get('model')} "
                      f"latency={e.get('latency_ms')}ms "
                      f"in={e.get('input_tokens')} out={e.get('output_tokens')}"
                      f"{' [red]ERR[/red]' if e.get('error') else ''}")
        if e.get("error"):
            console.print(f"  error: {e['error']}")


@app.command()
def viewer(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host."),
    port: int = typer.Option(7437, "--port", help="Bind port."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code change (dev)."),
):
    """Launch the trace viewer at http://host:port. Auto-picks the latest run; live updates via SSE."""
    PATHS.ensure()
    import uvicorn
    console.print(f"[green]viewer[/green] → http://{host}:{port}")
    uvicorn.run(
        "perturb.viewer.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="warning",
    )


if __name__ == "__main__":
    PATHS.ensure()
    app()
