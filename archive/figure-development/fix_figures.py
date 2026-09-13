from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
OUT = Path(__file__).resolve().parent / "figures"
plt.rcParams.update({'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'figure.titlesize':11,'pdf.fonttype':42,'ps.fonttype':42})
COL={'blue':'#4C78A8','orange':'#F58518','green':'#54A24B','red':'#E45756','purple':'#B279A2','gray':'#8C8C8C','dark':'#2E3440'}
# dataset composition (remove overlapping suptitle/axes title)
provider_counts={'GPT':83,'Grok':92,'Gemini':125}
fig, axes=plt.subplots(1,2,figsize=(7.2,2.35),gridspec_kw={'width_ratios':[1.1,1.0]})
ax=axes[0]
ax.bar(list(provider_counts.keys()), list(provider_counts.values()), color=[COL['blue'],COL['orange'],COL['green']])
ax.set_ylabel('records'); ax.set_title('Selected perturber')
for i,(k,v) in enumerate(provider_counts.items()): ax.text(i,v+3,str(v),ha='center',va='bottom',fontweight='bold')
ax.set_ylim(0,140); ax.spines[['top','right']].set_visible(False)
ax=axes[1]
ax.bar(['300-record pool'], [275], color=COL['green'], label='validated')
ax.bar(['300-record pool'], [25], bottom=[275], color=COL['red'], label='diagnostic')
ax.text(0, 137.5, '275\nvalidated', ha='center', va='center', color='white', fontweight='bold')
ax.text(0, 287.5, '25', ha='center', va='center', color='white', fontweight='bold')
ax.set_ylim(0,320); ax.set_ylabel('records'); ax.set_title('Validation status')
ax.legend(frameon=False, loc='upper left')
ax.spines[['top','right']].set_visible(False)
fig.tight_layout(w_pad=1.6)
fig.savefig(OUT/'dataset_composition_big.pdf',bbox_inches='tight',pad_inches=0.04); plt.close(fig)
# localization: shorten titles and widen gap
judges=['GPT','Grok','Gemini']; gens=['GPT','Grok','Gemini']
loc_cit=np.array([[94.0,95.4,95.0],[98.4,98.3,98.5],[95.3,95.5,97.3]])
loc_val=np.array([[75.4,71.0,83.6],[76.5,74.2,82.4],[76.8,72.8,81.5]])
fig,axes=plt.subplots(1,2,figsize=(7.6,2.75),sharey=True)
for ax,mat,title,vmin in [(axes[0],loc_cit,'Citation locality',92),(axes[1],loc_val,'Replacement in wrong claim',68)]:
    im=ax.imshow(mat,vmin=vmin,vmax=100,cmap='BuGn')
    ax.set_xticks(np.arange(3),gens); ax.set_yticks(np.arange(3),judges)
    ax.set_title(title, pad=8)
    for i in range(3):
        for j in range(3): ax.text(j,i,f'{mat[i,j]:.1f}',ha='center',va='center',fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.68)
axes[0].set_ylabel('Judge')
fig.tight_layout(w_pad=2.0)
fig.savefig(OUT/'localization_large.pdf',bbox_inches='tight',pad_inches=0.04); plt.close(fig)
# cell audit findings: shorten title and avoid crowding
cell_labels=['FP','TN','TP','FN']
stack_data={'valid/genuine':[0,31,21,6],'alternate error':[22,0,0,0],'adoption-label issue':[2,0,1,3],'unclear/wrong reason':[1,0,1,0]}
colors=[COL['green'],COL['blue'],COL['orange'],COL['gray']]
fig,ax=plt.subplots(figsize=(5.4,2.65))
bot=np.zeros(len(cell_labels))
for (lab,vals),c in zip(stack_data.items(),colors):
    vals=np.array(vals); ax.bar(cell_labels, vals, bottom=bot, label=lab, color=c); bot+=vals
for i,total in enumerate(bot): ax.text(i,total+0.7,int(total),ha='center',fontweight='bold',fontsize=8)
ax.set_ylabel('reviewed cases'); ax.set_title('Human evaluation: 88/153 reviewed', pad=8)
ax.legend(frameon=False,ncols=2,bbox_to_anchor=(0.5,-0.18),loc='upper center')
ax.spines[['top','right']].set_visible(False)
fig.savefig(OUT/'cell_audit_findings.pdf',bbox_inches='tight',pad_inches=0.04); plt.close(fig)
print('fixed')
