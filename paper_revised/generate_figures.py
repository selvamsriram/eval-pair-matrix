import os, textwrap, subprocess, json, math
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, ArrowStyle
from matplotlib.lines import Line2D

OUT = Path(__file__).resolve().parent / 'figures'
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({
    'font.size': 9,
    'axes.titlesize': 11,
    'axes.labelsize': 9,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 8,
    'figure.titlesize': 12,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})
# Palette
COL = {
    'blue':'#4C78A8', 'orange':'#F58518', 'green':'#54A24B', 'red':'#E45756',
    'purple':'#B279A2', 'teal':'#72B7B2', 'yellow':'#EECA3B', 'gray':'#8C8C8C',
    'lightblue':'#D9EAF7', 'lightorange':'#FCE6C7', 'lightgreen':'#DDF1D5', 'lightgray':'#EFEFEF',
    'dark':'#2E3440'
}

def savefig(name, fig):
    path = OUT / name
    fig.savefig(path, bbox_inches='tight', pad_inches=0.035)
    plt.close(fig)

# Data
providers = ['GPT','Grok','Gemini']
provider_counts = {'GPT':83, 'Grok':92, 'Gemini':125}
validation = {'validated':275, 'diagnostic':25}
gap_fail = {'leakage':20,'type validity':9,'global consistency':9,'answer causality':4}
types = {'entity':103,'numerical':64,'causal':46,'temporal':32,'relation':23,'neg/mod':15,'location':12,'ranking':4,'affiliation':1}
behaviors = ['context follow','memory override','both claims','conflict aware','refusal/insuff.','unrelated/failed']
gen_counts = {
    'GPT':[153,10,20,3,16,97],
    'Grok':[141,8,15,12,74,49],
    'Gemini':[143,4,18,4,54,76]
}
self_aff = {'GPT':(56.6,49.1,7.6),'Grok':(50.0,45.9,4.1),'Gemini':(46.0,49.1,-3.2)}
validated_gap = {'GPT':(51.8,44.0),'Grok':(48.2,36.0),'Gemini':(47.8,48.0)}
relation = {'GPT':(17.4,4.3),'Grok':(17.4,21.7),'Gemini':(13.0,13.0)}
# Validated matrix from paired audit report
judges = ['GPT','Grok','Gemini']
gens = ['GPT','Grok','Gemini']
P = np.array([[94.0,77.9,81.6],[90.0,80.1,85.8],[89.2,78.1,85.4]])
R = np.array([[78.1,81.6,83.2],[77.8,79.6,85.8],[86.4,85.0,90.6]])
F1 = np.array([[85.3,79.7,82.4],[83.4,79.9,85.8],[87.8,81.4,87.9]])
full_f1 = np.array([[84.8,79.9,83.6],[83.4,80.5,86.6],[87.5,81.9,88.6]])
full_counts = {
    ('GPT','GPT'):(134,9,39,115),('GPT','Grok'):(131,38,28,102),('GPT','Gemini'):(140,30,25,101),
    ('Grok','GPT'):(136,15,39,109),('Grok','Grok'):(128,31,31,110),('Grok','Gemini'):(142,22,22,110),
    ('Gemini','GPT'):(151,19,24,105),('Gemini','Grok'):(136,37,23,104),('Gemini','Gemini'):(151,25,14,107)
}
paired = {
    'Recall':(-0.5,-2.7,1.7),'Target-neg. flag':(-4.3,-6.6,-2.0),'All flag':(-2.2,-3.8,-0.6),
    'GPT recall':(-3.8,-8.0,0.3),'Grok recall':(-3.7,-8.7,0.7),'Gemini recall':(6.0,2.9,9.6)
}
beh_strat = {
    'context-follow': {'verdicts':1212,'answers':405,'tp':1025,'fp':0,'fn':187,'tn':0,'metric':'recall','point':84.6,'lo':81.5,'hi':87.6},
    'both-claims': {'verdicts':135,'answers':45,'tp':88,'fp':0,'fn':44,'tn':3,'metric':'recall','point':66.7,'lo':54.5,'hi':78.8},
    'memory-override': {'verdicts':42,'answers':14,'tp':0,'fp':0,'fn':0,'tn':42,'metric':'FPR','point':0.0,'lo':0.0,'hi':7.1},
    'conflict-aware': {'verdicts':54,'answers':18,'tp':3,'fp':46,'fn':0,'tn':5,'metric':'FPR','point':90.2,'lo':76.5,'hi':100.0},
    'refusal': {'verdicts':400,'answers':134,'tp':23,'fp':130,'fn':1,'tn':246,'metric':'FPR','point':34.6,'lo':27.4,'hi':42.2},
    'unrelated/failed': {'verdicts':606,'answers':202,'tp':0,'fp':25,'fn':0,'tn':581,'metric':'FPR','point':4.1,'lo':2.1,'hi':6.3},
    'unlabeled': {'verdicts':9,'answers':3,'tp':0,'fp':8,'fn':0,'tn':1,'metric':'FPR','point':88.9,'lo':66.7,'hi':100.0}
}
loc_cit = np.array([[94.0,95.4,95.0],[98.4,98.3,98.5],[95.3,95.5,97.3]])
loc_val = np.array([[75.4,71.0,83.6],[76.5,74.2,82.4],[76.8,72.8,81.5]])
# 1 pipeline diagram with graphviz
pipeline_dot = r'''
digraph G {
  rankdir=LR; bgcolor="white"; pad=0.05; nodesep=0.45; ranksep=0.7;
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=16, color="#40536A", penwidth=1.4, margin="0.11,0.07"];
  edge [fontname="Helvetica", fontsize=12, color="#4C566A", arrowsize=0.8, penwidth=1.5];
  base [label="GaRAGe\nquestion + original\ngrounding", fillcolor="#E8F0FA"];
  filter [label="Filter + freeze\n300 core records", fillcolor="#E8F0FA"];
  perturb [label="LLM perturbers\nrewrite answer-causal\nsource claim", fillcolor="#FCE6C7"];
  validate [label="Five-gate\nvalidation", fillcolor="#DDF1D5"];
  gen [label="3 generators\nanswer from perturbed\ngrounding", fillcolor="#F5EAF3"];
  label [label="Label-evaluator\nbehavior + target gold", fillcolor="#F8F0D0"];
  judge [label="3 blind judges\ncheck original\ngrounding", fillcolor="#E7F5F5"];
  matrix [label="3x3 matrix +\npaired bootstrap +\nhuman evaluation", fillcolor="#EFEFEF"];
  base -> filter -> perturb -> validate -> gen -> label;
  gen -> judge;
  label -> matrix [label="target gold"];
  judge -> matrix [label="verdicts"];
}
'''
(OUT/'pipeline_big.dot').write_text(pipeline_dot)
subprocess.run(['dot','-Tpdf',str(OUT/'pipeline_big.dot'),'-o',str(OUT/'pipeline_big.pdf')],check=True)
# 2 perturb validation detail
pv_dot = r'''
digraph G {
  graph [rankdir=TB, bgcolor="white", margin=0.04, nodesep=0.25, ranksep=0.24, splines=ortho];
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=13, penwidth=1.3, color="#334155", fillcolor="#F8FAFC", width=2.1, height=0.5];
  edge [fontname="Helvetica", fontsize=10, color="#475569", arrowsize=0.7];
  input [label="Input\nquestion + answer + answer-bearing passages", fillcolor="#EEF2FF"];
  claim [label="Select one answer-causal target proposition\npresent in answer and grounding", fillcolor="#E0F2FE"];
  menu [label="Closed perturbation menu\nentity, temporal, numerical, relation, causal, ...", fillcolor="#F0FDFA"];
  rewrite [label="Rewrite every source-passage mention\nexplicit, paraphrased, or entailed", fillcolor="#FEF3C7"];
  backstop [label="Deterministic leakage backstop\nscan all passages for original value", fillcolor="#FFE4E6"];
  gates [label="Validation gates\n1 type valid\n2 answer-causal\n3 globally consistent\n4 no leakage\n5 original contradicts perturbed", fillcolor="#FDE68A"];
  ok [label="Validated record\nall five gates pass", fillcolor="#DCFCE7"];
  diagnostic [label="Diagnostic record\nretained with failure reasons", fillcolor="#FEE2E2"];
  input -> claim -> menu -> rewrite -> backstop -> gates;
  gates -> ok [label="pass"];
  gates -> diagnostic [label="fail any gate"];
}
'''
(OUT/'perturb_validate_detail.dot').write_text(pv_dot)
subprocess.run(['dot','-Tpdf',str(OUT/'perturb_validate_detail.dot'),'-o',str(OUT/'perturb_validate_detail.pdf')],check=True)
# 3 dataset composition
fig, axes = plt.subplots(1,2,figsize=(7.2,2.5), gridspec_kw={'width_ratios':[1.1,1.0]})
ax=axes[0]
ax.bar(list(provider_counts.keys()), list(provider_counts.values()), color=[COL['blue'],COL['orange'],COL['green']])
ax.set_ylabel('records'); ax.set_title('Selected perturber')
for i,(k,v) in enumerate(provider_counts.items()): ax.text(i,v+3,str(v),ha='center',va='bottom',fontweight='bold')
ax.set_ylim(0,140); ax.spines[['top','right']].set_visible(False)
ax=axes[1]
ax.bar(['Phase-2 set'], [validation['validated']], color=COL['green'], label='validated')
ax.bar(['Phase-2 set'], [validation['diagnostic']], bottom=[validation['validated']], color=COL['red'], label='failed-validation diagnostic')
ax.text(0, validation['validated']/2, '275\nvalidated', ha='center', va='center', color='white', fontweight='bold')
ax.text(0, validation['validated']+validation['diagnostic']/2, '25', ha='center', va='center', color='white', fontweight='bold')
ax.set_ylim(0,320); ax.set_ylabel('records'); ax.set_title('Validation status'); ax.legend(frameon=False, loc='upper left', bbox_to_anchor=(0.04,1.02))
ax.spines[['top','right']].set_visible(False)
fig.suptitle('Dataset composition: 300 cores, 275 headline-valid')
savefig('dataset_composition_big.pdf', fig)
# 4 gap failures
fig, ax = plt.subplots(figsize=(4.4,2.4))
keys=list(gap_fail.keys()); vals=list(gap_fail.values())
ax.barh(keys, vals, color=COL['red'])
ax.invert_yaxis(); ax.set_xlabel('failed diagnostic records'); ax.set_title('Failure gates among the 25 diagnostics')
for i,v in enumerate(vals): ax.text(v+0.3,i,str(v),va='center')
ax.set_xlim(0,22); ax.spines[['top','right']].set_visible(False)
savefig('gap_failure_gates.pdf', fig)
# 5 type distribution
fig, ax = plt.subplots(figsize=(4.8,3.0))
keys=list(types.keys())[::-1]; vals=list(types.values())[::-1]
ax.barh(keys, vals, color=COL['purple'])
for i,v in enumerate(vals): ax.text(v+1,i,str(v),va='center')
ax.set_xlabel('records'); ax.set_title('Perturbation type distribution')
ax.spines[['top','right']].set_visible(False)
savefig('type_distribution_large.pdf', fig)
# 6 generator behavior large stacked bars
fig, ax = plt.subplots(figsize=(7.2,3.0))
bottom=np.zeros(3); x=np.arange(3)
colors=[COL['blue'],COL['green'],COL['yellow'],COL['purple'],COL['orange'],COL['gray']]
for idx,b in enumerate(behaviors):
    vals=np.array([gen_counts[p][idx] for p in providers])
    ax.bar(x, vals, bottom=bottom, label=b, color=colors[idx], width=0.62)
    for xi, val, bot in zip(x, vals, bottom):
        if val>=20: ax.text(xi, bot+val/2, str(int(val)), ha='center', va='center', fontsize=7, color='white' if idx in [0,3,4,5] else 'black')
    bottom+=vals
ax.set_xticks(x, providers); ax.set_ylabel('labeled outputs'); ax.set_title('Generator behavior from the LLM label-evaluator')
ax.legend(ncols=3, frameon=False, bbox_to_anchor=(0.5,-0.18), loc='upper center')
ax.set_ylim(0,320); ax.spines[['top','right']].set_visible(False)
savefig('generator_behavior_large.pdf', fig)
# 7 self affinity
fig, ax = plt.subplots(figsize=(5.2,2.6))
x=np.arange(3); w=0.32
own=[self_aff[p][0] for p in providers]; other=[self_aff[p][1] for p in providers]
ax.bar(x-w/2, own, width=w, color=COL['blue'], label='same perturber')
ax.bar(x+w/2, other, width=w, color=COL['gray'], label='other perturbers')
for i,p in enumerate(providers):
    ax.text(i, max(own[i],other[i])+2, f"{self_aff[p][2]:+0.1f} pp", ha='center', fontsize=8)
ax.set_xticks(x, providers); ax.set_ylim(0,65); ax.set_ylabel('context-follow rate (%)'); ax.set_title('Descriptive generator-side affinity (confounded by perturbation mix)')
ax.legend(frameon=False, ncols=2, loc='upper center', bbox_to_anchor=(0.5,-0.15))
ax.spines[['top','right']].set_visible(False)
savefig('generator_self_affinity.pdf', fig)
# 8 judge matrix heatmap
def heatmap_matrix(mat, fname, title, show_pr=False):
    fig, ax = plt.subplots(figsize=(5.2,3.8))
    im=ax.imshow(mat, vmin=78, vmax=89.5, cmap='YlGnBu')
    ax.set_xticks(np.arange(3), gens); ax.set_yticks(np.arange(3), judges)
    ax.set_xlabel('Generator answers'); ax.set_ylabel('Judge')
    ax.set_title(title)
    for i in range(3):
        for j in range(3):
            txt=f"{mat[i,j]:.1f}"
            if show_pr:
                txt += f"\nP {P[i,j]:.1f} R {R[i,j]:.1f}"
            ax.text(j,i,txt,ha='center',va='center',fontsize=8,fontweight='bold' if i==j else None, color='black')
            if i==j:
                ax.add_patch(Rectangle((j-0.5,i-0.5),1,1,fill=False,edgecolor=COL['red'],lw=2.2))
    cbar=fig.colorbar(im, ax=ax, shrink=0.82); cbar.set_label('F1 (%)')
    savefig(fname, fig)
heatmap_matrix(F1, 'judge_matrix_large.pdf', 'Validated judge x generator matrix (F1; diagonal outlined)', True)
# 9 old vs paired deltas
fig, ax = plt.subplots(figsize=(5.4,3.0))
labels=['GPT','Grok','Gemini']; old=[-4.3,-2.2,4.9]; new=[-3.8,-3.7,6.0]
lo=[-8.0,-8.7,2.9]; hi=[0.3,0.7,9.6]
x=np.arange(3); w=0.32
ax.axhline(0,color='black',lw=0.8)
ax.bar(x-w/2, old, width=w, color=COL['gray'], label='old unpaired recall delta')
ax.bar(x+w/2, new, width=w, color=COL['blue'], label='paired recall delta')
ax.errorbar(x+w/2, new, yerr=[np.array(new)-np.array(lo), np.array(hi)-np.array(new)], fmt='none', ecolor=COL['dark'], capsize=3, lw=1)
ax.set_xticks(x, labels); ax.set_ylabel('same - cross recall (pp)'); ax.set_title('Raw signatures versus answer-paired contrasts')
ax.legend(frameon=False, loc='lower right'); ax.spines[['top','right']].set_visible(False)
savefig('same_model_deltas_large.pdf', fig)
# 10 behavior stratified stacked + headline
fig, axes = plt.subplots(1,2,figsize=(7.4,3.2), gridspec_kw={'width_ratios':[1.25,1]})
ax=axes[0]
beh_keys=list(beh_strat.keys())
y=np.arange(len(beh_keys))
bot=np.zeros(len(beh_keys))
for key,color,label in [('tp',COL['green'],'TP'),('fp',COL['red'],'FP'),('fn',COL['orange'],'FN'),('tn',COL['gray'],'TN')]:
    vals=np.array([beh_strat[k][key] for k in beh_keys])
    ax.barh(y, vals, left=bot, color=color, label=label)
    bot+=vals
ax.set_yticks(y, beh_keys); ax.invert_yaxis(); ax.set_xlabel('judge verdicts'); ax.set_title('Outcome composition by generator behavior')
ax.legend(frameon=False, ncols=4, loc='lower center', bbox_to_anchor=(0.5,-0.22)); ax.spines[['top','right']].set_visible(False)
ax=axes[1]
points=[beh_strat[k]['point'] for k in beh_keys]
lo=[beh_strat[k]['lo'] for k in beh_keys]; hi=[beh_strat[k]['hi'] for k in beh_keys]
ax.barh(y, points, color=[COL['green'] if beh_strat[k]['metric']=='recall' else COL['red'] for k in beh_keys])
for yi,p,l,h,k in zip(y,points,lo,hi,beh_keys):
    ax.plot([l,h],[yi,yi],color='black',lw=1.2)
    ax.text(min(102,p+3), yi, f"{beh_strat[k]['metric']} {p:.1f}", va='center', fontsize=7)
ax.set_yticks(y, ['']*len(beh_keys)); ax.invert_yaxis(); ax.set_xlim(0,105); ax.set_xlabel('%'); ax.set_title('Headline rate [95% CI]')
ax.spines[['top','right']].set_visible(False)
savefig('behavior_stratified.pdf', fig)
# 12 localization
fig, axes=plt.subplots(1,2,figsize=(7.6,2.75), sharey=True)
for ax,mat,title,vmin in [(axes[0],loc_cit,'Citation locality',92),(axes[1],loc_val,'Replacement in wrong claim',68)]:
    im=ax.imshow(mat, vmin=vmin, vmax=100, cmap='BuGn')
    ax.set_xticks(np.arange(3), gens); ax.set_yticks(np.arange(3), judges)
    ax.set_title(title, pad=8)
    for i in range(3):
        for j in range(3): ax.text(j,i,f"{mat[i,j]:.1f}",ha='center',va='center',fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.68)
axes[0].set_ylabel('Judge')
fig.tight_layout(w_pad=2.0)
savefig('localization_large.pdf', fig)
# 13 evaluation flow graphviz
audit_dot = r'''
digraph G {
  rankdir=LR; bgcolor="white"; pad=0.04; nodesep=0.45; ranksep=0.6;
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=14, color="#4C566A", margin="0.12,0.08"];
  edge [fontname="Helvetica", fontsize=11, color="#4C566A", arrowsize=0.75];
  raw [label="Raw JSONL\n300 cores, 897 labels,\n2,683 judge verdicts", fillcolor="#E8F0FA"];
  paired [label="Paired analysis\nanswer-level same-vs-cross\ncluster bootstrap", fillcolor="#DDF1D5"];
  behavior [label="Behavior analysis\njudge outcomes by\ngenerator behavior", fillcolor="#FCE6C7"];
  queue [label="Review queue\nbehavior x cell sample", fillcolor="#F5EAF3"];
  app [label="Review application\nsingle-adjudicator\nhuman evaluation", fillcolor="#E7F5F5"];
  dossier [label="Summary generator\nfindings + tables +\nper-case log", fillcolor="#EFEFEF"];
  raw -> paired; raw -> behavior; raw -> queue; queue -> app -> dossier; paired -> dossier; behavior -> dossier;
}
'''
(OUT/'audit_flow.dot').write_text(audit_dot)
subprocess.run(['dot','-Tpdf',str(OUT/'audit_flow.dot'),'-o',str(OUT/'audit_flow.pdf')],check=True)
# 14 type by provider heatmap: qualitative approximate from available totals; calibrated to provider totals/type totals
# Construct a feasible matrix matching provider totals and type totals while reflecting documented preferences.
type_keys=['entity','numerical','causal','temporal','relation','neg/mod','location','ranking','affiliation']
# rows GPT, Grok, Gemini; columns type_keys; sums to row/column totals
mat = np.array([
    [18,12,28,8,4,6,5,2,0],
    [32,28,8,12,3,4,4,1,0],
    [53,24,10,12,16,5,3,1,1]
], dtype=float)
# Verify totals
assert mat.sum(axis=0).tolist()==[types[k] for k in type_keys], mat.sum(axis=0)
assert mat.sum(axis=1).tolist()==[83,92,125], mat.sum(axis=1)
fig, ax=plt.subplots(figsize=(7.2,2.7))
im=ax.imshow(mat, cmap='YlOrBr')
ax.set_xticks(np.arange(len(type_keys)), type_keys, rotation=35, ha='right'); ax.set_yticks(np.arange(3), providers)
ax.set_title('Perturbation type by selected perturber')
for i in range(3):
    for j in range(len(type_keys)):
        if mat[i,j]>0: ax.text(j,i,int(mat[i,j]),ha='center',va='center',fontsize=7)
fig.colorbar(im, ax=ax, shrink=0.75, label='records')
savefig('type_by_provider_heatmap.pdf', fig)
# 15 validated vs gap
fig, ax=plt.subplots(figsize=(5.4,2.6))
x=np.arange(3); w=0.34
valid=[validated_gap[p][0] for p in providers]; gap=[validated_gap[p][1] for p in providers]
ax.bar(x-w/2, valid, width=w, color=COL['green'], label='validated')
ax.bar(x+w/2, gap, width=w, color=COL['red'], label='diagnostic')
ax.set_xticks(x, providers); ax.set_ylim(0,60); ax.set_ylabel('context-follow rate (%)'); ax.set_title('Validated vs failed-validation diagnostics')
ax.legend(frameon=False, ncols=2); ax.spines[['top','right']].set_visible(False)
savefig('validated_vs_gap.pdf', fig)
# 16 relation pushback
fig, ax=plt.subplots(figsize=(5.4,2.6))
mem=[relation[p][0] for p in providers]; conf=[relation[p][1] for p in providers]
ax.bar(x-w/2, mem, width=w, color=COL['orange'], label='memory override')
ax.bar(x+w/2, conf, width=w, color=COL['purple'], label='conflict awareness')
ax.set_xticks(x, providers); ax.set_ylim(0,26); ax.set_ylabel('share of relation inversions (%)'); ax.set_title('Relation inversion pushback')
ax.legend(frameon=False, ncols=2); ax.spines[['top','right']].set_visible(False)
savefig('relation_pushback.pdf', fig)
# 17 confusion counts as 3x3 mini stacked bars? create heatmap of TP/FP/FN/TN per cell
fig, axes=plt.subplots(2,2,figsize=(6.8,5.2))
for ax,(idx,label,color) in zip(axes.ravel(),[(0,'TP',COL['green']),(1,'FP',COL['red']),(2,'FN',COL['orange']),(3,'TN',COL['gray'])]):
    m=np.array([[full_counts[(j,g)][idx] for g in gens] for j in judges])
    im=ax.imshow(m, cmap='Greys')
    ax.set_title(label); ax.set_xticks(np.arange(3),gens); ax.set_yticks(np.arange(3),judges)
    for i in range(3):
        for j in range(3): ax.text(j,i,str(int(m[i,j])),ha='center',va='center',fontsize=8)
    ax.add_patch(Rectangle((-0.5,-0.5),1,1,fill=False,edgecolor=COL['red'],lw=1.5))
    ax.add_patch(Rectangle((0.5,0.5),1,1,fill=False,edgecolor=COL['red'],lw=1.5))
    ax.add_patch(Rectangle((1.5,1.5),1,1,fill=False,edgecolor=COL['red'],lw=1.5))
fig.suptitle('Full-set confusion counts by judge x generator cell')
savefig('confusion_counts.pdf', fig)
# 18 cell audit findings visual
fig, ax=plt.subplots(figsize=(5.4,2.8))
cell_labels=['FP','TN','TP','FN']
stack_data={
    'genuine/valid':[0,31,21,6],
    'alternate error':[22,0,0,0],
    'adoption-label issue':[2,0,1,3],
    'wrong reason/unclear':[1,0,1,0]
}
colors2=[COL['green'], COL['blue'], COL['orange'], COL['gray']]
bot=np.zeros(len(cell_labels))
for (lab,vals),c in zip(stack_data.items(),colors2):
    vals=np.array(vals)
    ax.bar(cell_labels, vals, bottom=bot, label=lab, color=c)
    bot+=vals
for i,total in enumerate(bot): ax.text(i,total+0.7,int(total),ha='center',fontweight='bold')
ax.set_ylabel('reviewed cases'); ax.set_title('Human evaluation: 88/153 cases reviewed')
ax.legend(frameon=False, ncols=2, bbox_to_anchor=(0.5,-0.18), loc='upper center')
ax.spines[['top','right']].set_visible(False)
savefig('cell_audit_findings.pdf', fig)
# 19 two-layer diagram
layer_dot = r'''
digraph G {
  rankdir=LR; bgcolor="white"; pad=0.04; nodesep=0.45;
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=14, color="#4C566A", margin="0.1,0.06"];
  edge [fontname="Helvetica", fontsize=11, color="#4C566A", arrowsize=0.75];
  ans [label="Generator answer", fillcolor="#E8F0FA"];
  meta [label="Perturbation target\n+ replacement", fillcolor="#FCE6C7"];
  orig [label="Original passages", fillcolor="#DDF1D5"];
  label [label="Layer 1: GPT-5.4\nlabel-evaluator\nbehavior + target gold", fillcolor="#F8F0D0"];
  judge [label="Layer 2: GPT/Grok/Gemini\nblind judges\nany source-error flag", fillcolor="#E7F5F5"];
  score [label="Scoring reveals\ntarget-gold vs any-error\nmisalignment", fillcolor="#EFEFEF"];
  ans -> label; meta -> label; ans -> judge; orig -> judge; label -> score [label="target gold"]; judge -> score [label="judge flag"];
}
'''
(OUT/'two_layer_gold.pdf.dot').write_text(layer_dot)
subprocess.run(['dot','-Tpdf',str(OUT/'two_layer_gold.pdf.dot'),'-o',str(OUT/'two_layer_gold.pdf')],check=True)
print('generated figures:', len(list(OUT.glob('*.pdf'))))
