#!/usr/bin/env python3
"""Rebuild *new* E7 DC and session-aware vector figures from processed E7 results.
This script reads only archived numerical results, not the raw CU8 files.
"""
from pathlib import Path
from zipfile import ZipFile
import io
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parent
fig=root/'figures'
fig.mkdir(exist_ok=True)
plt.rcParams.update({
    'font.family':'DejaVu Sans','font.size':7,'axes.labelsize':8,
    'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,
    'pdf.fonttype':42,'savefig.bbox':'tight'
})

with ZipFile(root/'data'/'E7_DC_resultados.zip') as z:
    c=pd.read_csv(io.BytesIO(z.read('contrasts_dc.csv')))
sub=c[(c['method']=='dc_removed')&(c['mask_dc_khz'].isin([5.0,10.0]))].copy()
sub['pair']=sub['on']+'/'+sub['off']
labels=['ON1/OFF1','ON2/OFF1','ON2/OFF2','ON3/OFF2']
positions=np.arange(4)
width=.36
fig_,ax=plt.subplots(figsize=(3.40,2.25))
for shift,mask in [(-.5,5.0),(.5,10.0)]:
    y=sub[sub['mask_dc_khz']==mask].set_index('pair').loc[labels]['band_minus_sideband_db'].values
    ax.bar(positions+shift*width,y,width,label=f'Exclusion $\\pm${int(mask)} kHz',alpha=.82)
ax.axhline(0,color='0.25',lw=.7)
ax.set_xticks(positions,labels,fontsize=6.4)
ax.set_ylabel('Local ON/OFF feature (dB)')
ax.set_ylim(0,0.080)
ax.legend(loc='upper right',frameon=False,fontsize=6.1)
ax.grid(axis='y',alpha=.18)
fig_.tight_layout(pad=.35)
fig_.savefig(fig/'e7_dc_mask_robustness.pdf')
plt.close(fig_)

with ZipFile(root/'data'/'E7_DC_resultados.zip') as z:
    windows=pd.read_csv(io.BytesIO(z.read('windows_dc.csv')))
summary=(windows[(windows['method']=='dc_removed') & (windows['mask_dc_khz']==5.0)]
         .groupby('capture')['local_feature_db'].agg(['mean','std']))
order=['A1','ON1','OFF1','ON2','OFF2','ON3','A2']
fig_,ax=plt.subplots(figsize=(3.40,2.22))
for i,cap in enumerate(order):
    v=summary.loc[cap]
    style = ('o','tab:blue') if 'ON' in cap else (('s','tab:orange') if 'OFF' in cap else ('^','tab:green'))
    ax.errorbar([i],[float(v['mean'])],yerr=[float(v['std'])],fmt=style[0],
                markersize=4,capsize=2,color=style[1],elinewidth=.8)
ax.axhline(0,color='0.30',lw=.7)
ax.set_xticks(range(len(order)),order,fontsize=6.5)
ax.set_ylabel('DC-corrected local feature (dB)')
ax.set_ylim(-.027,.083)
ax.grid(axis='y',alpha=.18)
fig_.tight_layout(pad=.35)
fig_.savefig(fig/'e7_capture_dc_features.pdf')
plt.close(fig_)
print('Generated new vector figures.')
