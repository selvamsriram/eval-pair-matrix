import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
GATES=["type_valid","answer_causal","global_context_consistent","no_original_answer_leakage","original_contradicts_perturbed"]
LABEL_RUNS={"GPT":"data/runs/20260531-005101-gen-gpt55-300/05_label_eval.jsonl","Grok":"data/runs/20260531-005112-gen-grok-300/05_label_eval.jsonl","Gemini":"data/runs/20260531-005123-gen-gemini-300/05_label_eval.jsonl"}
JUDGE_RUNS={"GPT_on_GPT":"data/runs/20260531-175601-judge-gpt-on-gpt/06_judge.jsonl","Gemini_on_Gemini":"data/runs/20260531-230857-judge-gemini-on-gemini/06_judge.jsonl","GPT_on_Grok":"data/runs/20260531-212107-judge-gpt-on-grok/06_judge.jsonl","Grok_on_GPT":"data/runs/20260531-175608-judge-grok-on-gpt/06_judge.jsonl"}
def rows(p):
    return [json.loads(x) for x in (ROOT/p).read_text(encoding="utf-8").splitlines() if x.strip()]
def passes(r):
    v=r.get("validation") or {}
    return all(v.get(g) is True for g in GATES)
def compact(s,n=520):
    s=re.sub(r"\s+"," ",(s or "")).strip()
    return s if len(s)<=n else s[:n-1]+"…"
def snippet(text,terms=(),n=520):
    text=re.sub(r"\s+"," ",(text or "")).strip()
    low=text.lower(); pos=-1
    for t in terms:
        if t:
            pos=low.find(str(t).lower())
            if pos>=0: break
    if pos<0: return compact(text,n)
    start=max(0,pos-n//2); end=min(len(text),start+n)
    start=max(0,end-n)
    pre="…" if start>0 else ""; post="…" if end<len(text) else ""
    return pre+text[start:end]+post
def provider(r): return ((r.get("generators") or {}).get("perturb") or {}).get("provider","unknown")
def passage_by_id(passages,pid):
    for p in passages or []:
        if p.get("passage_id")==pid: return p.get("text") or ""
    return ""
def first_mod_record(r):
    mids=r.get("modified_passage_ids") or []
    pid=mids[0] if mids else None
    if pid is None and r.get("doc_modifications"):
        pid=r["doc_modifications"][0].get("passage_id")
    return pid

def perturb_example(r):
    pid=first_mod_record(r)
    return {"core_id":r.get("core_id"),"question":compact(r.get("question"),300),"human_answer":compact(r.get("answer_generate"),450),"perturber_provider":provider(r),"perturbation_type":r.get("perturbation_type"),"original_value":r.get("original_value"),"perturbed_value":r.get("perturbed_value"),"atomic_claim_original":compact(r.get("atomic_claim_original"),320),"atomic_claim_perturbed":compact(r.get("atomic_claim_perturbed"),320),"validation_passes":passes(r),"validation_gates":{g:(r.get("validation") or {}).get(g) for g in GATES},"example_passage_id":pid,"original_passage_snippet":snippet(passage_by_id(r.get("all_grounding_original"),pid),(r.get("original_value"),),600),"perturbed_passage_snippet":snippet(passage_by_id(r.get("all_grounding_perturbed"),pid),(r.get("perturbed_value"),),600)}

core=rows(Path("data/exp/3provider_300.jsonl"))
out={"perturbation_examples":{},"generation_examples":{},"judge_examples":{}}
for name,cond in {"relation_inversion_valid":lambda r:r.get("perturbation_type")=="relation_inversion" and passes(r),"numerical_shift_valid":lambda r:r.get("perturbation_type")=="numerical_shift" and passes(r),"entity_substitution_valid":lambda r:r.get("perturbation_type")=="entity_substitution" and passes(r),"gap_fill_leakage_failure":lambda r:not passes(r) and (r.get("validation") or {}).get("no_original_answer_leakage") is not True}.items():
    rec=next((r for r in core if cond(r)),None)
    if rec: out["perturbation_examples"][name]=perturb_example(rec)

def gen_example(r,g):
    pid=first_mod_record(r)
    ev=g.get("llm_eval") or {}
    return {"core_id":r.get("core_id"),"question":compact(r.get("question"),300),"generator_provider":g.get("generator_provider"),"generator_model":g.get("generator_model"),"behavior_label":ev.get("behavior_label"),"entails_original_claim":ev.get("entails_original_claim"),"entails_perturbed_claim":ev.get("entails_perturbed_claim"),"is_refusal":g.get("is_refusal"),"cited_passage_ids":g.get("cited_passage_ids"),"original_value":r.get("original_value"),"perturbed_value":r.get("perturbed_value"),"answer":compact(g.get("answer_text"),650),"label_rationale":compact(ev.get("rationale"),420),"modified_passage_id":pid,"modified_passage_snippet":snippet(passage_by_id(r.get("all_grounding_perturbed"),pid),(r.get("perturbed_value"),),500)}

def find_gen(label, prefer_model=None, ptype=None):
    for model,path in LABEL_RUNS.items():
        if prefer_model and model!=prefer_model: continue
        for r in rows(Path(path)):
            if ptype and r.get("perturbation_type")!=ptype: continue
            for g in r.get("generator_outputs") or []:
                ev=g.get("llm_eval") or {}
                if ev.get("behavior_label")==label:
                    return gen_example(r,g)
for key,args in {"context_follow_gpt":{"label":"context_follow","prefer_model":"GPT"},"memory_override_any":{"label":"memory_override"},"grok_refusal":{"label":"refusal_or_insufficient","prefer_model":"Grok"},"relation_inversion_conflict":{"label":"conflict_awareness","ptype":"relation_inversion"}}.items():
    ex=find_gen(**args)
    if ex: out["generation_examples"][key]=ex

def judge_example(r,v,cell):
    g=(r.get("generator_outputs") or [{}])[0]
    sid=v.get("supporting_source_passage_id")
    try: sid_int=int(sid) if sid is not None else None
    except Exception: sid_int=None
    return {"cell":cell,"core_id":r.get("core_id"),"question":compact(r.get("question"),300),"generator_provider":v.get("generator_provider"),"generator_model":v.get("generator_model"),"judge_provider":v.get("judge_provider"),"judge_model":v.get("judge_model"),"pair_type":v.get("pair_type"),"gold_has_induced_error":v.get("gold_has_induced_error"),"gold_target_original":v.get("gold_perturbation_target"),"gold_replacement_perturbed":v.get("gold_perturbation_replacement"),"generator_answer":compact(g.get("answer_text"),650),"judge_verdict":v.get("verdict"),"contains_factual_error":v.get("contains_factual_error"),"wrong_claim":compact(v.get("wrong_claim"),450),"supporting_source_passage_id":sid,"judge_explanation":compact(v.get("explanation"),550),"confidence":v.get("confidence"),"source_passage_snippet":snippet(passage_by_id(r.get("all_grounding_original"),sid_int),(v.get("gold_perturbation_target"),v.get("wrong_claim")),600)}

def find_judge(kind,cell_filter=None):
    for cell,path in JUDGE_RUNS.items():
        if cell_filter and cell!=cell_filter: continue
        for r in rows(Path(path)):
            for v in r.get("judge_verdicts") or []:
                gold=bool(v.get("gold_has_induced_error")); pred=bool(v.get("contains_factual_error"))
                ok=(kind=="tp" and gold and pred) or (kind=="fn" and gold and not pred) or (kind=="fp" and (not gold) and pred) or (kind=="tn" and (not gold) and not pred)
                if ok: return judge_example(r,v,cell)
for key,kind,cell in [("true_positive_same_model","tp","Gemini_on_Gemini"),("false_negative","fn","GPT_on_GPT"),("false_positive","fp","Grok_on_GPT"),("true_negative","tn","GPT_on_Grok")]:
    ex=find_judge(kind,cell)
    if ex: out["judge_examples"][key]=ex
Path("examples_report.json").write_text(json.dumps(out,indent=2,sort_keys=True),encoding="utf-8")
print(json.dumps(out,indent=2,sort_keys=True)[:50000])
