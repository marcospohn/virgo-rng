#!/usr/bin/env python3
"""Regenerate the E5 Sagittarius figure from archived processed E5 data."""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
# Reconstruct E5 diagram from archived E5 processed numeric spectrum, rather than generating synthetic data.
d=pd.read_csv(ROOT/'data/e5_processed.csv')
x=d['frequency_hz'].to_numpy()/1e6
y1=d['ON1_broad_residual_db'].to_numpy()
y2=d['ON2_broad_residual_db'].to_numpy()
figm, (ax1,ax2)=plt.subplots(1,2, figsize=(11.0,3.6), gridspec_kw={'width_ratios':[1.4,1]})
for ax in (ax1,ax2):
    ax.plot(x,y1,lw=1.2,label='ON1 / OFF')
    ax.plot(x,y2,lw=1.2,label='ON2 / OFF')
    ax.grid(alpha=.25)
    ax.set_ylabel('Local-baseline residual (dB)')
    ax.set_xlabel('RF frequency (MHz)')
ax1.set_xlim(1419.205752,1421.605166)
ax1.set_ylim(-.22,.36)
ax1.set_title('(a) Receiver band')
ax1.legend(loc='upper right',fontsize=8)
ax2.set_xlim(1420.24,1420.43)
ax2.set_ylim(-.06,.34)
ax2.set_title('(b) Candidate near 1420.331 MHz')
ax2.axvspan(1420.3125879375,1420.3500879375,alpha=.17,label='Shared >0.25 dB')
ax2.axhline(.25,lw=.6,linestyle=':')
figm.tight_layout(pad=1.15)
figm.savefig(fig/'e5_sagittarius.pdf',bbox_inches='tight')
plt.close(figm)
print('Merged related work into v3, restored 4 embedded product images, rebuilt E5 vector plot')
