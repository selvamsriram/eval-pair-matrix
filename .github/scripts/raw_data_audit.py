import json,re
from pathlib import Path
from collections import Counter,defaultdict

ROOT=Path(__file__).resolve().parents[2]
GATES=["type_valid","answer_causal","global_context_consistent","no_original_answer_leakage","original_contradicts_perturbed"]
LABEL_RUNS={"GPT":"data/runs/20260531-005101-gen-gpt55-300/05_label_eval.jsonl","Grok":"data/runs/20260531-005112-gen-grok-300/05_label_eval.jsonl","Gemini":"data/runs/20260531-005123-gen-gemini-300/05_label_eval.jsonl"}
JUDGE_RUNS={("GPT","GPT"):"data/runs/20260531-175601-judge-gpt-on-gpt/06_judge.jsonl",("Grok","GPT"):"data/runs/20260531-175608-judge-grok-on-gpt/06_judge.jsonl",("Gemini","GPT"):"data/runs/20260531-175617-judge-gemini-on-gpt/06_judge.jsonl",("GPT","Grok"):"data/runs/20260531-212107-judge-gpt-on-grok/06_judge.jsonl",("Grok","Grok"):"data/runs/20260531-212359-judge-grok-on-grok/06_judge.jsonl",("Gemini","Grok"):"data/runs/20260531-212120-judge-gemini-on-grok/06_judge.jsonl",("GPT","Gemini"):"data/runs/20260531-230842-judge-gpt-on-gemini/06_judge.jsonl",("Grok","Gemini"):"data/runs/20260531-230848-judge-grok-on-gemini/06_judge.jsonl",("Gemini","Gemini"):"data/runs/20260531-230857-judge-gemini-on-gemini/06_judge.jsonl"}
def rows(p):
    return [json.loads(x) for x in (ROOT/p).read_text(encoding="utf-8").splitlines() if x.strip()]
def passes(r):
    v=r.get("validation") or {}
    return all(v.get(g) is True for g in GATES)
def pct(n,d): return None if not d else round(100*n/d,3)
def prf(tp,fp,fn):
    p=tp/(tp+fp) if tp+fp else 0; r=tp/(tp+fn) if tp+fn else 0
    f=2*p*r/(p+r) if p+r else 0
    return round(100*p,3),round(100*r,3),round(100*f,3)
norm_re=re.compile(r"[\s\W_]+")
def norm(s): return norm_re.sub(" ",(s or "").lower()).strip()

report={"files":{}}
core=rows(Path("data/exp/3provider_300.jsonl")); report["files"]["data/exp/3provider_300.jsonl"]=len(core)
pc=Counter(); tc=Counter(); fail=Counter(); valid=0
for r in core:
    pc[((r.get("generators") or {}).get("perturb") or {}).get("provider","unknown")]+=1
    tc[r.get("perturbation_type") or "unknown"]+=1
    if passes(r): valid+=1
    else:
        v=r.get("validation") or {}
        for g in GATES:
            if v.get(g) is not True: fail[g]+=1
report["core"]={"n":len(core),"unique_core_ids":len({r.get("core_id") for r in core}),"validated":valid,"gap_fill":len(core)-valid,"providers":dict(pc),"types":dict(tc),"gap_fail_gates":dict(fail)}

gen_summary={}; self_aff={}; val_gap={}; type_push={}; total_outputs=total_eval=0
for gen,path in LABEL_RUNS.items():
    rs=rows(Path(path)); report["files"][path]=len(rs)
    labels=Counter(); outputs=evals=0; own_t=own_cf=oth_t=oth_cf=0; val_t=val_cf=gap_t=gap_cf=0; self_ref=llm_ref=0; cf_den=cf_cite=0
    bytype=defaultdict(lambda:Counter())
    for r in rs:
        pert=((r.get("generators") or {}).get("perturb") or {}).get("provider","unknown")
        mod=set(r.get("modified_passage_ids") or []); good=passes(r); typ=r.get("perturbation_type") or "unknown"
        for g in r.get("generator_outputs") or []:
            outputs+=1
            ev=g.get("llm_eval")
            if not ev: continue
            evals+=1; lab=ev.get("behavior_label") or "missing"; labels[lab]+=1
            if g.get("is_refusal"): self_ref+=1
            if lab=="refusal_or_insufficient": llm_ref+=1
            cf=lab=="context_follow"
            if g.get("generator_provider")==pert: own_t+=1; own_cf+=cf
            else: oth_t+=1; oth_cf+=cf
            if good: val_t+=1; val_cf+=cf
            else: gap_t+=1; gap_cf+=cf
            if cf:
                cf_den+=1; cf_cite+=bool(set(g.get("cited_passage_ids") or []) & mod)
            bytype[typ]["n"]+=1; bytype[typ]["cf"]+=cf; bytype[typ]["mem"]+=(lab=="memory_override"); bytype[typ]["conf"]+=(lab=="conflict_awareness")
    total_outputs+=outputs; total_eval+=evals
    gen_summary[gen]={"outputs":outputs,"llm_eval":evals,"labels":dict(labels),"rates":{k:pct(v,evals) for k,v in labels.items()},"self_declared_refusals":self_ref,"llm_refusals":llm_ref,"cf_cited_modified":[cf_cite,cf_den,pct(cf_cite,cf_den)]}
    self_aff[gen]={"own":[own_cf,own_t,pct(own_cf,own_t)],"others":[oth_cf,oth_t,pct(oth_cf,oth_t)],"delta_pp":round((pct(own_cf,own_t) or 0)-(pct(oth_cf,oth_t) or 0),3)}
    val_gap[gen]={"validated":[val_cf,val_t,pct(val_cf,val_t)],"gap":[gap_cf,gap_t,pct(gap_cf,gap_t)],"delta_pp":round((pct(val_cf,val_t) or 0)-(pct(gap_cf,gap_t) or 0),3)}
    type_push[gen]={t:{"n":c["n"],"mem_pct":pct(c["mem"],c["n"]),"conf_pct":pct(c["conf"],c["n"]),"cf_pct":pct(c["cf"],c["n"])} for t,c in bytype.items()}
report["generator"]={"total_outputs":total_outputs,"total_llm_eval":total_eval,"summary":gen_summary,"self_affinity":self_aff,"validated_vs_gap":val_gap,"type_pushback":type_push}

cells={}; total_verdicts=0; pairs=Counter()
for (judge,gen),path in JUDGE_RUNS.items():
    rs=rows(Path(path)); report["files"][path]=len(rs)
    tp=fp=tn=fn=n=gold_pos=0; wc_n=wc_d=cit_n=cit_d=0
    for r in rs:
        mods=set(r.get("modified_passage_ids") or [])
        for v in r.get("judge_verdicts") or []:
            n+=1; total_verdicts+=1; pairs[v.get("pair_type","missing")]+=1
            gold=bool(v.get("gold_has_induced_error")); pred=bool(v.get("contains_factual_error")); gold_pos+=gold
            if gold and pred:
                tp+=1
                repl=v.get("gold_perturbation_replacement") or ""; wc=v.get("wrong_claim") or ""
                if repl and wc: wc_d+=1; wc_n+=norm(repl) in norm(wc)
                sid=v.get("supporting_source_passage_id")
                if sid is not None:
                    cit_d+=1
                    try: sid=int(sid)
                    except Exception: sid=None
                    cit_n+=sid in mods
            elif (not gold) and pred: fp+=1
            elif gold and not pred: fn+=1
            else: tn+=1
    p,r,f=prf(tp,fp,fn)
    cells[f"{judge}_on_{gen}"]={"n":n,"gold_pos":gold_pos,"tp":tp,"fp":fp,"tn":tn,"fn":fn,"precision":p,"recall":r,"f1":f,"wrong_claim_contains":[wc_n,wc_d,pct(wc_n,wc_d)],"citation_locality":[cit_n,cit_d,pct(cit_n,cit_d)]}
row={j:round(sum(cells[f"{j}_on_{g}"]["f1"] for g in ["GPT","Grok","Gemini"])/3,3) for j in ["GPT","Grok","Gemini"]}
col={g:round(sum(cells[f"{j}_on_{g}"]["f1"] for j in ["GPT","Grok","Gemini"])/3,3) for g in ["GPT","Grok","Gemini"]}
diag=[cells[f"{x}_on_{x}"]["f1"] for x in ["GPT","Grok","Gemini"]]
off=[cells[f"{j}_on_{g}"]["f1"] for j in ["GPT","Grok","Gemini"] for g in ["GPT","Grok","Gemini"] if j!=g]
same={}
for j in ["GPT","Grok","Gemini"]:
    own=cells[f"{j}_on_{j}"]; cross=[cells[f"{j}_on_{g}"] for g in ["GPT","Grok","Gemini"] if g!=j]
    same[j]={"f1_own":own["f1"],"f1_cross":round(sum(c["f1"] for c in cross)/2,3),"f1_delta":round(own["f1"]-sum(c["f1"] for c in cross)/2,3),"recall_own":own["recall"],"recall_cross":round(sum(c["recall"] for c in cross)/2,3),"recall_delta":round(own["recall"]-sum(c["recall"] for c in cross)/2,3),"precision_own":own["precision"],"precision_cross":round(sum(c["precision"] for c in cross)/2,3)}
report["judge"]={"total_verdicts":total_verdicts,"cells":cells,"row_avg_f1":row,"col_avg_f1":col,"diag_avg_f1":round(sum(diag)/3,3),"offdiag_avg_f1":round(sum(off)/6,3),"diag_minus_offdiag":round(sum(diag)/3-sum(off)/6,3),"same_effects":same,"pair_types":dict(pairs)}
assert report["core"]["n"]==300 and report["core"]["unique_core_ids"]==300
assert total_outputs==900 and total_eval==897 and total_verdicts==2683
Path("audit_report.json").write_text(json.dumps(report,indent=2,sort_keys=True),encoding="utf-8")
print("AUDIT_JSON_START")
print(json.dumps(report,indent=2,sort_keys=True)[:60000])
print("AUDIT_JSON_END")
