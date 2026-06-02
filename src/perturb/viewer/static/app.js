// perturb · viewer — single-page client. Vanilla JS, no build step.

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const state = {
  runs: [],
  currentRunId: null,
  records: [],
  filtered: [],
  selectedCoreId: null,
  detail: null,        // {record, diffs, trace_events}
  activeTab: 'overview',
  search: '',
  liveOk: false,
  pendingRefresh: null,
};

const TABS = [
  { id: 'overview',      label: 'Overview' },
  { id: 'original',      label: 'Original' },
  { id: 'perturbed',     label: 'Perturbed' },
  { id: 'diff',          label: 'Diff' },
  { id: 'modifications', label: 'Modifications' },
  { id: 'validation',    label: 'Validation' },
  { id: 'generation',    label: 'Generation' },
  { id: 'traces',        label: 'Traces' },
];

// ---------- API ----------

async function api(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

async function loadRuns({ keepSelection = false } = {}) {
  const data = await api('/api/runs');
  state.runs = data.runs;
  const picker = $('#run-picker');
  picker.innerHTML = '';
  for (const r of state.runs) {
    const opt = document.createElement('option');
    opt.value = r.run_id;
    const steps = r.steps_present.length ? ` · ${r.steps_present.join('→')}` : '';
    opt.textContent = `${r.run_id}${steps}`;
    picker.appendChild(opt);
  }
  if (!keepSelection || !state.runs.find(r => r.run_id === state.currentRunId)) {
    state.currentRunId = data.latest;
  }
  if (state.currentRunId) {
    picker.value = state.currentRunId;
    await loadRecords();
  } else {
    $('#record-list').innerHTML = `<div class="p-8 text-center text-sm text-zinc-500">no runs yet — run <code class="text-emerald-400">perturb runs new</code></div>`;
  }
}

async function loadRecords() {
  if (!state.currentRunId) return;
  try {
    const data = await api(`/api/runs/${state.currentRunId}/records`);
    state.records = data.records;
  } catch (e) {
    state.records = [];
  }
  applyFilter();
  $('#record-count').textContent = `${state.records.length} records`;
  // Re-resolve selection
  if (state.selectedCoreId && !state.records.find(r => r.core_id === state.selectedCoreId)) {
    state.selectedCoreId = null;
    state.detail = null;
    renderDetail();
  } else if (state.selectedCoreId) {
    loadRecordDetail(state.selectedCoreId);
  }
}

async function loadRecordDetail(coreId) {
  if (!state.currentRunId) return;
  state.selectedCoreId = coreId;
  try {
    state.detail = await api(`/api/runs/${state.currentRunId}/records/${encodeURIComponent(coreId)}`);
  } catch (e) {
    state.detail = null;
  }
  renderRecordList();
  renderDetail();
}

// ---------- Rendering: tabs + record list ----------

function applyFilter() {
  const q = state.search.trim().toLowerCase();
  state.filtered = q
    ? state.records.filter(r =>
        (r.question || '').toLowerCase().includes(q) ||
        (r.core_id || '').toLowerCase().includes(q) ||
        (r.latest_behavior_label || '').toLowerCase().includes(q) ||
        (r.latest_generator || '').toLowerCase().includes(q))
    : state.records.slice();
  renderRecordList();
}

function statusDot(r) {
  if (r.validation_passes === true)  return '<span class="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400"></span>';
  if (r.validation_passes === false) return '<span class="inline-block w-1.5 h-1.5 rounded-full bg-rose-400"></span>';
  if ((r.last_step_status || '').startsWith('failed'))  return '<span class="inline-block w-1.5 h-1.5 rounded-full bg-rose-400"></span>';
  if ((r.last_step_status || '').startsWith('skipped')) return '<span class="inline-block w-1.5 h-1.5 rounded-full bg-amber-400"></span>';
  if (r.last_step_status === 'ok')                       return '<span class="inline-block w-1.5 h-1.5 rounded-full bg-sky-400"></span>';
  return '<span class="inline-block w-1.5 h-1.5 rounded-full bg-zinc-600"></span>';
}

function renderRecordList() {
  const list = $('#record-list');
  if (!state.filtered.length) {
    list.innerHTML = `<div class="p-8 text-center text-sm text-zinc-500">no records${state.search ? ' match' : ''}</div>`;
    return;
  }
  list.innerHTML = state.filtered.map(r => `
    <div class="record-row ${r.core_id === state.selectedCoreId ? 'active' : ''} px-3 py-2.5 border-b border-ink-700/60 border-l-2 border-l-transparent cursor-pointer"
         data-cid="${escapeHtml(r.core_id)}">
      <div class="flex items-center gap-2">
        ${statusDot(r)}
        <span class="font-mono text-[11px] text-zinc-400">${escapeHtml(r.core_id.replace(/^garage_core_/, ''))}</span>
        <span class="ml-auto text-[10px] uppercase tracking-wide text-zinc-500">${escapeHtml(r.last_step || '')}</span>
      </div>
      <div class="mt-1 text-sm text-zinc-200 line-clamp-2">${escapeHtml(r.question || '(no question)')}</div>
      <div class="mt-1 flex flex-wrap items-center gap-1.5">
        ${r.perturbation_type ? `<span class="text-[10px] font-mono text-emerald-400/80">${escapeHtml(r.perturbation_type)}</span>` : ''}
        ${r.generation_count ? `<span class="text-[10px] font-mono text-sky-300/90">gen:${r.generation_count}</span>` : ''}
        ${r.latest_behavior_label ? `<span class="text-[10px] font-mono ${behaviorTextClass(r.latest_behavior_label)}">${escapeHtml(r.latest_behavior_label)}</span>` : ''}
      </div>
    </div>
  `).join('');
  list.querySelectorAll('[data-cid]').forEach(el => {
    el.addEventListener('click', () => loadRecordDetail(el.dataset.cid));
  });
}

function renderTabs() {
  const evCount = state.detail?.trace_events?.length || 0;
  const genCount = state.detail?.record?.generator_outputs?.length || 0;
  $('#tabs').innerHTML = TABS.map(t => {
    const count = t.id === 'traces' && evCount ? `<span class="count">${evCount}</span>`
                : t.id === 'generation' && genCount ? `<span class="count">${genCount}</span>`
                : '';
    return `<button class="tab-btn ${t.id === state.activeTab ? 'active' : ''}" data-tab="${t.id}">${t.label}${count}</button>`;
  }).join('');
  $$('#tabs .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      state.activeTab = btn.dataset.tab;
      renderTabs();
      renderDetail();
    });
  });
}

// ---------- Rendering: detail panel ----------

function renderDetail() {
  renderTabs();
  const root = $('#detail');
  if (!state.detail) {
    root.innerHTML = `<div class="text-sm text-zinc-500">select a record on the left</div>`;
    return;
  }
  const r = state.detail.record;
  switch (state.activeTab) {
    case 'overview':      root.innerHTML = renderOverview(r); break;
    case 'original':      root.innerHTML = renderPassages(r.all_grounding_original, { highlightValue: r.original_value, mark: 'removed' }); break;
    case 'perturbed':     root.innerHTML = renderPassages(r.all_grounding_perturbed, { highlightValue: r.perturbed_value, mark: 'added' }); break;
    case 'diff':          root.innerHTML = renderDiff(r, state.detail.diffs); break;
    case 'modifications': root.innerHTML = renderModifications(r); break;
    case 'validation':    root.innerHTML = renderValidation(r); break;
    case 'generation':    root.innerHTML = renderGeneration(r); break;
    case 'traces':        root.innerHTML = renderTraces(state.detail.trace_events); wireTraceToggles(); break;
  }
}

function renderOverview(r) {
  const ps = r.pipeline_state || {};
  const chips = Object.entries(ps).map(([k, v]) => {
    const cls = v === 'ok' ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
              : v.startsWith('failed') ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
              : 'bg-amber-500/15 text-amber-300 border-amber-500/30';
    return `<span class="px-2 py-0.5 rounded-md text-xs font-mono border ${cls}">${escapeHtml(k)}: ${escapeHtml(v)}</span>`;
  }).join('');
  const meta = [
    r.question_category && `<span class="tag">cat: ${escapeHtml(r.question_category)}</span>`,
    r.question_complexity && `<span class="tag">complexity: ${escapeHtml(r.question_complexity)}</span>`,
    r.question_popularity && `<span class="tag">pop: ${escapeHtml(r.question_popularity)}</span>`,
    r.question_type && `<span class="tag">type: ${escapeHtml(r.question_type)}</span>`,
  ].filter(Boolean).join('');
  const latestGen = (r.generator_outputs || []).slice(-1)[0];
  return `
    <div class="space-y-6 max-w-4xl">
      <div>
        <div class="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">core_id</div>
        <div class="font-mono text-sm text-zinc-300">${escapeHtml(r.core_id)} <span class="text-zinc-500">·</span> <span class="text-zinc-500">garage:</span> ${escapeHtml(r.garage_sample_id || '')}</div>
      </div>
      <div>
        <div class="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">question</div>
        <div class="text-lg leading-snug">${escapeHtml(r.question)}</div>
        <div class="mt-3 flex flex-wrap gap-1.5 text-xs">${meta.replace(/class="tag"/g, 'class="px-2 py-0.5 rounded-md font-mono border bg-ink-800 border-ink-700 text-zinc-400"')}</div>
      </div>
      <div>
        <div class="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">human answer</div>
        <div class="text-sm leading-relaxed text-zinc-200 bg-ink-850 border border-ink-700 rounded-md p-3">${escapeHtml(r.answer_generate || '(none)')}</div>
      </div>
      ${latestGen ? `
      <div>
        <div class="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">latest generation</div>
        <div class="bg-ink-850 border border-ink-700 rounded-md p-3">
          <div class="flex flex-wrap items-center gap-2 text-xs">
            <span class="font-mono text-sky-300">${escapeHtml(latestGen.generator_provider || '')}/${escapeHtml(latestGen.generator_model || '')}</span>
            <span class="font-mono text-zinc-400">${escapeHtml(latestGen.mode || '')}</span>
            ${behaviorChip(latestGen.behavior_label)}
            ${latestGen.is_refusal ? '<span class="px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono">refusal</span>' : ''}
          </div>
          <div class="mt-2 text-sm leading-relaxed text-zinc-200">${highlightGeneratedAnswer(latestGen.answer_text || '', r)}</div>
        </div>
      </div>` : ''}
      ${r.perturbation_type ? `
      <div class="grid grid-cols-2 gap-4">
        <div>
          <div class="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">perturbation</div>
          <div class="bg-ink-850 border border-ink-700 rounded-md p-3 space-y-2">
            <div class="font-mono text-sm">
              <span class="text-emerald-400">${escapeHtml(r.perturbation_type)}</span>${r.perturbation_subtype ? `<span class="text-zinc-500"> · </span><span class="text-zinc-300">${escapeHtml(r.perturbation_subtype)}</span>` : ''}
            </div>
            <div class="text-sm flex items-center gap-2">
              <span class="mark-removed font-mono">${escapeHtml(r.original_value || '')}</span>
              <span class="text-zinc-500">→</span>
              <span class="mark-added font-mono">${escapeHtml(r.perturbed_value || '')}</span>
            </div>
            <div class="text-xs text-zinc-400">plausibility: <span class="text-zinc-200">${escapeHtml(r.plausibility || '—')}</span></div>
          </div>
        </div>
        <div>
          <div class="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">atomic claim</div>
          <div class="bg-ink-850 border border-ink-700 rounded-md p-3 space-y-2 text-sm">
            <div><span class="text-zinc-500 text-xs">original</span><div class="text-zinc-200">${escapeHtml(r.atomic_claim_original || '—')}</div></div>
            <div><span class="text-zinc-500 text-xs">perturbed</span><div class="text-zinc-200">${escapeHtml(r.atomic_claim_perturbed || '—')}</div></div>
          </div>
        </div>
      </div>
      ${r.deducibility_note ? `<div><div class="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">deducibility note</div><div class="text-sm text-zinc-300 italic">${escapeHtml(r.deducibility_note)}</div></div>` : ''}
      ` : ''}
      <div>
        <div class="text-[11px] uppercase tracking-wider text-zinc-500 mb-2">pipeline state</div>
        <div class="flex flex-wrap gap-1.5">${chips || '<span class="text-zinc-500 text-sm">—</span>'}</div>
      </div>
    </div>`;
}

function renderGeneration(r) {
  const outputs = r.generator_outputs || [];
  if (!outputs.length) return `<div class="text-sm text-zinc-500">(no generator outputs yet)</div>`;
  const summary = summarizeGeneration(outputs);
  return `
    <div class="space-y-4 max-w-6xl">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
        ${Object.entries(summary).map(([label, count]) => `
          <div class="border border-ink-700 bg-ink-850/40 rounded-md px-3 py-2">
            <div class="text-[10px] uppercase tracking-wider text-zinc-500">${escapeHtml(label.replaceAll('_', ' '))}</div>
            <div class="mt-1 text-lg font-mono ${behaviorTextClass(label)}">${count}</div>
          </div>`).join('')}
      </div>
      ${outputs.map((o, idx) => renderGenerationOutput(o, idx, r)).join('')}
    </div>`;
}

function renderGenerationOutput(o, idx, r) {
  return `
    <div class="border border-ink-700 rounded-md bg-ink-850/40 overflow-hidden">
      <div class="px-3 py-2 border-b border-ink-700 flex flex-wrap items-center gap-2 text-xs">
        <span class="font-mono text-zinc-500">#${idx + 1}</span>
        <span class="font-mono text-sky-300">${escapeHtml(o.generator_provider || '')}/${escapeHtml(o.generator_model || '')}</span>
        <span class="font-mono text-zinc-400">${escapeHtml(o.mode || '')}</span>
        ${o.sample_id ? `<span class="font-mono text-zinc-500">sample ${escapeHtml(o.sample_id)}</span>` : ''}
        ${behaviorChip(o.behavior_label)}
        ${o.is_refusal ? '<span class="px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono">refusal</span>' : ''}
        <span class="ml-auto font-mono text-zinc-500">${escapeHtml(formatEpoch(o.completed_at))}</span>
      </div>
      <div class="p-3 space-y-3">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
          <div class="border border-ink-700 rounded-md px-2.5 py-2">
            <div class="text-zinc-500 mb-1">original claim</div>
            ${boolChip(o.entails_original_claim)}
          </div>
          <div class="border border-ink-700 rounded-md px-2.5 py-2">
            <div class="text-zinc-500 mb-1">perturbed claim</div>
            ${boolChip(o.entails_perturbed_claim)}
          </div>
          <div class="border border-ink-700 rounded-md px-2.5 py-2">
            <div class="text-zinc-500 mb-1">cited passages</div>
            <div class="flex flex-wrap gap-1">${citationChips(o.cited_passage_ids)}</div>
          </div>
        </div>
        <div>
          <div class="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">answer</div>
          <div class="text-sm leading-relaxed text-zinc-100 bg-ink-900 border border-ink-700 rounded-md p-3">${highlightGeneratedAnswer(o.answer_text || '', r)}</div>
        </div>
        ${o.notes ? `
        <div>
          <div class="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">notes</div>
          <div class="text-sm text-zinc-300 italic">${escapeHtml(o.notes)}</div>
        </div>` : ''}
        <details>
          <summary class="text-xs text-zinc-500 cursor-pointer hover:text-zinc-300">show raw generator output</summary>
          <pre class="wrap mt-2 text-xs text-zinc-300 bg-ink-900 border border-ink-700 rounded p-2">${escapeHtml(prettyJson(o))}</pre>
        </details>
      </div>
    </div>`;
}

function renderPassages(passages, opts = {}) {
  if (!passages || !passages.length) return `<div class="text-sm text-zinc-500">(no passages)</div>`;
  return `<div class="space-y-3 max-w-4xl">` + passages.map(p => `
    <div class="border ${p.was_modified ? 'border-emerald-500/30 bg-emerald-500/[0.03]' : 'border-ink-700 bg-ink-850/40'} rounded-md p-3">
      <div class="flex items-center gap-2 text-[11px] mb-2">
        <span class="font-mono text-zinc-400">#${p.passage_id}</span>
        <span class="text-zinc-500">·</span>
        <span class="font-mono text-zinc-500">${escapeHtml(p.evidence_correct || '—')}</span>
        ${p.evidence_cited === 'YES' ? '<span class="font-mono text-emerald-400">cited</span>' : ''}
        ${p.was_modified ? '<span class="ml-auto px-1.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">modified</span>' : ''}
      </div>
      <div class="text-sm leading-relaxed text-zinc-200">${highlightSpan(p.text, opts.highlightValue, opts.mark)}</div>
    </div>`).join('') + `</div>`;
}

function renderDiff(r, diffs) {
  if (!diffs || !diffs.length) return `<div class="text-sm text-zinc-500">(no passages)</div>`;
  return `<div class="space-y-3 max-w-7xl">` + diffs.map(d => {
    const origHi = highlightSpan(d.original_text, r.original_value, 'removed');
    const pertHi = highlightSpan(d.perturbed_text, r.perturbed_value, 'added');
    return `
    <div class="border ${d.was_modified ? 'border-emerald-500/30' : 'border-ink-700'} rounded-md overflow-hidden">
      <div class="bg-ink-850 border-b border-ink-700 px-3 py-1.5 flex items-center gap-2 text-[11px]">
        <span class="font-mono text-zinc-400">#${d.passage_id}</span>
        <span class="font-mono text-zinc-500">${escapeHtml(d.label || '—')}</span>
        ${d.cited === 'YES' ? '<span class="font-mono text-emerald-400">cited</span>' : ''}
        ${d.was_modified ? '<span class="ml-auto px-1.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">modified</span>' : '<span class="ml-auto text-zinc-500 font-mono">unchanged</span>'}
        ${d.mod && !d.was_modified && d.mod.skip_reason ? `<span class="text-zinc-400 italic">${escapeHtml(d.mod.skip_reason)}</span>` : ''}
      </div>
      <div class="grid grid-cols-2 divide-x divide-ink-700">
        <div class="p-3 text-sm leading-relaxed bg-rose-500/[0.02]">
          <div class="text-[10px] uppercase tracking-wider text-rose-400/80 mb-1">original</div>
          <div class="text-zinc-200">${origHi}</div>
        </div>
        <div class="p-3 text-sm leading-relaxed bg-emerald-500/[0.02]">
          <div class="text-[10px] uppercase tracking-wider text-emerald-400/80 mb-1">perturbed</div>
          <div class="text-zinc-200">${pertHi}</div>
        </div>
      </div>
    </div>`;
  }).join('') + `</div>`;
}

function renderModifications(r) {
  const mods = r.doc_modifications || [];
  if (!mods.length) return `<div class="text-sm text-zinc-500">(no modifications yet)</div>`;
  return `<div class="space-y-2 max-w-4xl">` + mods.map(m => `
    <div class="border ${m.was_modified ? 'border-emerald-500/30' : 'border-ink-700'} rounded-md p-3 bg-ink-850/40">
      <div class="flex items-center gap-2 text-[11px] mb-2">
        <span class="font-mono text-zinc-400">#${m.passage_id}</span>
        ${m.was_modified
          ? `<span class="px-1.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">modified</span><span class="font-mono text-zinc-500">${escapeHtml(m.mention_kind || '')}</span>`
          : `<span class="px-1.5 rounded bg-zinc-500/20 text-zinc-300 font-mono">unchanged</span><span class="text-zinc-400 italic">${escapeHtml(m.skip_reason || '')}</span>`}
      </div>
      ${m.was_modified ? `
        <div class="text-sm flex items-center gap-2 mb-2">
          <span class="mark-removed font-mono">${escapeHtml(m.original_span || '')}</span>
          <span class="text-zinc-500">→</span>
          <span class="mark-added font-mono">${escapeHtml(m.perturbed_span || '')}</span>
        </div>
        ${m.modified_text ? `<details class="text-xs"><summary class="text-zinc-500 cursor-pointer hover:text-zinc-300">show full rewritten text</summary><pre class="wrap mt-2 p-2 bg-ink-900 border border-ink-700 rounded-md text-zinc-300">${escapeHtml(m.modified_text)}</pre></details>` : ''}
      ` : ''}
    </div>`).join('') + `</div>`;
}

function renderValidation(r) {
  const v = r.validation || {};
  const gates = [
    ['type_valid',                     'Type valid'],
    ['answer_causal',                  'Answer-causal'],
    ['global_context_consistent',      'Globally consistent'],
    ['no_original_answer_leakage',     'No leakage'],
    ['original_contradicts_perturbed', 'Original contradicts perturbed'],
  ];
  const chip = (val) => {
    if (val === true)  return '<span class="px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-xs font-mono">pass</span>';
    if (val === false) return '<span class="px-2 py-0.5 rounded-md bg-rose-500/15 text-rose-300 border border-rose-500/30 text-xs font-mono">fail</span>';
    return '<span class="px-2 py-0.5 rounded-md bg-zinc-500/15 text-zinc-400 border border-zinc-500/30 text-xs font-mono">—</span>';
  };
  return `
    <div class="space-y-4 max-w-3xl">
      <div class="grid grid-cols-1 gap-2">
        ${gates.map(([k, label]) => `
          <div class="flex items-center justify-between border border-ink-700 bg-ink-850/40 rounded-md px-3 py-2">
            <span class="text-sm">${label}</span>${chip(v[k])}
          </div>`).join('')}
      </div>
      <div class="flex items-center gap-3 text-sm">
        <span class="text-zinc-500">plausibility</span>
        <span class="font-mono text-zinc-200">${escapeHtml(v.plausibility || '—')}</span>
      </div>
      ${v.rejection_reasons && v.rejection_reasons.length ? `
      <div>
        <div class="text-[11px] uppercase tracking-wider text-rose-400/80 mb-1">rejection reasons</div>
        <ul class="list-disc list-inside text-sm text-rose-300 space-y-0.5">
          ${v.rejection_reasons.map(s => `<li>${escapeHtml(s)}</li>`).join('')}
        </ul>
      </div>` : ''}
    </div>`;
}

function renderTraces(events) {
  if (!events || !events.length) return `<div class="text-sm text-zinc-500">(no LLM trace events for this record yet)</div>`;
  return `<div class="space-y-3 max-w-5xl">` + events.map((e, i) => `
    <div class="border border-ink-700 rounded-md bg-ink-850/40">
      <div class="flex items-center gap-3 px-3 py-2 border-b border-ink-700 text-xs">
        <span class="font-mono text-emerald-400">${escapeHtml(e.step || '')}</span>
        <span class="font-mono text-zinc-400">${escapeHtml((e.event_id || '').slice(0, 8))}</span>
        <span class="text-zinc-500">${escapeHtml(e.provider || '')}/${escapeHtml(e.model || '')}</span>
        <span class="ml-auto flex items-center gap-3 text-zinc-400">
          ${e.latency_ms != null ? `<span><span class="text-zinc-500">latency</span> ${e.latency_ms}ms</span>` : ''}
          ${e.input_tokens != null ? `<span><span class="text-zinc-500">in</span> ${e.input_tokens}</span>` : ''}
          ${e.output_tokens != null ? `<span><span class="text-zinc-500">out</span> ${e.output_tokens}</span>` : ''}
          ${e.error ? '<span class="px-1.5 rounded bg-rose-500/20 text-rose-300 font-mono">error</span>' : ''}
        </span>
      </div>
      <div class="p-3 space-y-2">
        ${e.error ? `<pre class="wrap text-xs text-rose-300 bg-rose-500/10 border border-rose-500/30 rounded p-2">${escapeHtml(e.error)}</pre>` : ''}
        <details data-trace-section><summary class="text-xs text-zinc-400 cursor-pointer hover:text-zinc-200">system prompt</summary>
          <pre class="wrap mt-2 text-xs text-zinc-300 bg-ink-900 border border-ink-700 rounded p-2">${escapeHtml(e.system_prompt || '')}</pre></details>
        <details data-trace-section><summary class="text-xs text-zinc-400 cursor-pointer hover:text-zinc-200">user prompt</summary>
          <pre class="wrap mt-2 text-xs text-zinc-300 bg-ink-900 border border-ink-700 rounded p-2">${escapeHtml(e.user_prompt || '')}</pre></details>
        <details data-trace-section ${e.error ? 'open' : ''}><summary class="text-xs text-zinc-400 cursor-pointer hover:text-zinc-200">raw response</summary>
          <pre class="wrap mt-2 text-xs text-zinc-300 bg-ink-900 border border-ink-700 rounded p-2">${escapeHtml(e.raw_response || '')}</pre></details>
        <details data-trace-section ${i === events.length - 1 ? 'open' : ''}><summary class="text-xs text-zinc-400 cursor-pointer hover:text-zinc-200">parsed JSON</summary>
          <pre class="wrap mt-2 text-xs text-emerald-200 bg-ink-900 border border-ink-700 rounded p-2">${escapeHtml(prettyJson(e.parsed_output))}</pre></details>
      </div>
    </div>`).join('') + `</div>`;
}

function wireTraceToggles() { /* no-op for now; <details> handles itself */ }

// ---------- Helpers ----------

function summarizeGeneration(outputs) {
  const out = {};
  for (const o of outputs) {
    const label = o.behavior_label || 'unlabeled';
    out[label] = (out[label] || 0) + 1;
  }
  return out;
}

function behaviorTextClass(label) {
  switch (label) {
    case 'context_follow': return 'text-emerald-300';
    case 'memory_override': return 'text-rose-300';
    case 'both_claims': return 'text-amber-300';
    case 'conflict_awareness': return 'text-sky-300';
    case 'refusal_or_insufficient': return 'text-zinc-300';
    case 'unrelated_or_failed': return 'text-fuchsia-300';
    default: return 'text-zinc-400';
  }
}

function behaviorChip(label) {
  const classes = {
    context_follow: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    memory_override: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    both_claims: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    conflict_awareness: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    refusal_or_insufficient: 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30',
    unrelated_or_failed: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30',
  };
  const cls = classes[label] || 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30';
  return `<span class="px-2 py-0.5 rounded-md border text-xs font-mono ${cls}">${escapeHtml(label || 'unlabeled')}</span>`;
}

function boolChip(val) {
  if (val === true) return '<span class="px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-mono">yes</span>';
  if (val === false) return '<span class="px-2 py-0.5 rounded-md bg-zinc-500/15 text-zinc-300 border border-zinc-500/30 font-mono">no</span>';
  return '<span class="px-2 py-0.5 rounded-md bg-zinc-500/15 text-zinc-400 border border-zinc-500/30 font-mono">unknown</span>';
}

function citationChips(ids) {
  if (!ids || !ids.length) return '<span class="text-zinc-500">none</span>';
  return ids.map(id => `<span class="px-1.5 rounded bg-ink-800 border border-ink-700 text-zinc-300 font-mono">[${escapeHtml(id)}]</span>`).join('');
}

function formatEpoch(epoch) {
  if (!epoch) return '';
  try {
    return new Date(epoch * 1000).toLocaleString();
  } catch {
    return String(epoch);
  }
}

function highlightGeneratedAnswer(text, record) {
  let html = escapeHtml(text || '');
  const spans = [
    [record.original_value, 'mark-removed'],
    [record.perturbed_value, 'mark-added'],
  ].filter(([needle]) => needle);
  for (const [needle, cls] of spans) {
    const escapedNeedle = escapeHtml(needle);
    html = html.replace(
      new RegExp(escapeRegex(escapedNeedle), 'gi'),
      (m) => `<span class="${cls}">${m}</span>`
    );
  }
  return html;
}

function highlightSpan(text, needle, mark) {
  if (!text) return '';
  if (!needle) return escapeHtml(text);
  const cls = mark === 'added' ? 'mark-added' : 'mark-removed';
  return escapeHtml(text).replace(
    new RegExp(escapeRegex(escapeHtml(needle)), 'gi'),
    (m) => `<span class="${cls}">${m}</span>`
  );
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function escapeRegex(s) { return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
function prettyJson(v) { try { return JSON.stringify(v, null, 2); } catch { return String(v); } }

// ---------- SSE ----------

function startSse() {
  const es = new EventSource('/api/events');
  es.addEventListener('hello', () => setLive(true));
  es.addEventListener('fs', (e) => {
    setLive(true);
    let payload;
    try { payload = JSON.parse(e.data); } catch { return; }
    // Run added: refresh the run list (might be a brand-new run).
    if (payload.kind === 'step' || payload.kind === 'trace') {
      if (payload.run_id && payload.run_id === state.currentRunId) {
        scheduleRefresh();
      } else if (payload.run_id && !state.runs.find(r => r.run_id === payload.run_id)) {
        // brand new run dir — refresh run list, keep current selection
        loadRuns({ keepSelection: true });
      }
    }
  });
  es.onerror = () => {
    setLive(false);
    setTimeout(startSse, 2000);  // reconnect
    try { es.close(); } catch {}
  };
}

function scheduleRefresh() {
  if (state.pendingRefresh) return;
  state.pendingRefresh = setTimeout(async () => {
    state.pendingRefresh = null;
    await loadRecords();
  }, 250); // debounce burst writes
}

function setLive(ok) {
  state.liveOk = ok;
  const dot = $('#live-dot');
  const txt = $('#live-text');
  if (ok) {
    dot.className = 'inline-block w-2 h-2 rounded-full bg-emerald-400 live-on';
    txt.textContent = 'live';
    txt.className = 'text-emerald-300';
  } else {
    dot.className = 'inline-block w-2 h-2 rounded-full bg-rose-500';
    txt.textContent = 'reconnecting…';
    txt.className = 'text-zinc-400';
  }
}

// ---------- Boot ----------

$('#run-picker').addEventListener('change', async (e) => {
  state.currentRunId = e.target.value;
  state.selectedCoreId = null;
  state.detail = null;
  await loadRecords();
  renderDetail();
});

$('#record-search').addEventListener('input', (e) => {
  state.search = e.target.value;
  applyFilter();
});

(async function boot() {
  renderTabs();
  startSse();
  await loadRuns();
})();
