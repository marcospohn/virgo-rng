#!/usr/bin/env python3
"""Vector workflow schematic for the paper. It depicts processing, not measured results."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
P=Path(__file__).resolve().parent/'figures'/'pipeline_workflow_v8.pdf'
fig,ax=plt.subplots(figsize=(11.0,2.65))
ax.set_xlim(0,11.3);ax.set_ylim(0,2.65);ax.axis('off')
entries=[
  ('1. Source & provenance','CU8 I/Q, timestamps,\\nfrequency, sky/load metadata'),
  ('2. Spectral processing','8192-point FFT;\\nper-block DC subtraction'),
  ('3. Instrumental controls','Retuning; ON/OFF; loads;\\ncenter masks; baselines'),
  ('4. Statistical checks','10-s windows; uncertainty;\\nI/Q entropy & amplitude'),
]
# Use consistent monochrome-friendly outlines with muted gray fill
for i,(head,detail) in enumerate(entries):
    x=.28+i*2.72
    box=FancyBboxPatch((x,.54),2.45,1.52,boxstyle='round,pad=0.055,rounding_size=.12',
                       linewidth=1.1,edgecolor='#293446',facecolor='#f4f6f8')
    ax.add_patch(box)
    ax.text(x+1.225,1.69,head,fontsize=10.2,fontweight='bold',ha='center',va='center',color='#1f2937')
    ax.text(x+1.225,1.07,detail.replace('\\n','\n'),fontsize=8.7,ha='center',va='center',color='#414b58',linespacing=1.55)
    if i<3:
      ax.add_patch(FancyArrowPatch((x+2.46,1.28),(x+2.65,1.28),arrowstyle='-|>',mutation_scale=11,linewidth=1.0,color='#374151'))
ax.text(5.5,.18,'Products: spectra • ON/OFF contrasts • parameter-sensitivity tables • window statistics • reproducibility archive',
        fontsize=8.8,ha='center',va='center',color='#374151')
fig.savefig(P,bbox_inches='tight',pad_inches=.04)
plt.close(fig)
print(P)
