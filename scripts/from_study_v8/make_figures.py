#!/usr/bin/env python3
"""Recreate figures directly from the archived CSV/JSON summaries (no raw CU8 required).
All spectral results are exploratory and not calibrated brightness temperatures.
"""
from pathlib import Path
import zipfile, io, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
FIG=ROOT/'figures'; FIG.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.labelsize':8,'axes.titlesize':9,
                     'axes.spines.top':False,'axes.spines.right':False,'legend.fontsize':7,
                     'xtick.labelsize':7,'ytick.labelsize':7,'pdf.fonttype':42,'savefig.bbox':'tight'})

def readcsv(file, member):
    with zipfile.ZipFile(ROOT/'data'/file) as z:
        return pd.read_csv(io.BytesIO(z.read(member)))

def readjson(file, member):
    with zipfile.ZipFile(ROOT/'data'/file) as z:
        return json.loads(z.read(member))

def mov(x,n):
    return np.convolve(np.pad(x,(n//2,n//2),mode='reflect'),np.ones(n)/n,mode='valid')

# E2: retuning control; relative local excess only, no cross-tuning absolute power normalization.
fig,ax=plt.subplots(figsize=(3.45,2.42))
for idx,fc in enumerate([1420105752,1420405752,1420705752]):
    d=readcsv('E2_resultados.zip',f'results/E1_deslocamento/centro_{fc}_spectrum.csv')
    f=d.frequency_hz.values/1e6; pow_=d.power.values
    y=10*np.log10(np.maximum(pow_,1e-20)); y=y-mov(y,151)
    pick=(f>1419.950)&(f<1420.030)
    ax.plot(f[pick],y[pick],lw=1,label=f'{fc/1e6:.3f} MHz tuned')
ax.axvline(1419.9885645,ls='--',color='0.45',lw=.9)
ax.set(xlabel='Absolute RF frequency (MHz)',ylabel='Local spectral excess (dB)')
ax.ticklabel_format(axis='x',style='plain',useOffset=False)
ax.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter('%.3f'))
# Show five well-spaced frequency values rather than all automatic ticks.
ax.set_xticks([1419.95, 1419.97, 1419.99, 1420.01, 1420.03])
ax.tick_params(axis='x', labelsize=4)
ax.legend(frameon=False,fontsize=6,loc='upper right');ax.grid(alpha=.18)
fig.savefig(FIG/'e2_retuning.pdf');plt.close(fig)

# E4: direction test, narrow feature candidate was NOT directional.
fig,ax=plt.subplots(figsize=(3.45,2.30))
E4=[]
for file,member,label in [('E4_resultados.zip','results/E4_direcional/analysis/summary.json','E4'),
                          ('E4_repeticao.zip','results/E4_repeticao/analysis/summary.json','E4 repeat')]:
    d=readjson(file,member);E4.append([d['captures'][x]['excess_db'] for x in ['ON1','OFF','ON2']])
a=np.arange(3);width=.34
for i,vals in enumerate(E4):ax.bar(a+(i-.5)*width,vals,width,label=['First run','Repeat'][i])
ax.axhline(0,color='0.45',lw=.7)
ax.set_xticks(a,['ON1','OFF','ON2']);ax.set_ylabel('Local peak excess (dB)')
ax.legend(frameon=False,fontsize=7);ax.grid(axis='y',alpha=.18)
fig.savefig(FIG/'e4_direction.pdf');plt.close(fig)

# E6: reanalysis on the full raw contrasts with the same 35/341 channel approach.
fig,ax=plt.subplots(figsize=(3.45,2.38))
d=readcsv('E6_resultados.zip','results/E6_freq_switch/analysis/spectra_contrasts.csv')
E6_values={}
for pair,g in d.groupby('pair',sort=False):
    f=g.frequency_hz.to_numpy();y=g.raw_on_off_db.to_numpy()
    r=mov(y,35)-mov(mov(y,35),341)
    band=np.abs(f-1420392000)<=20000
    side=(np.abs(f-(1420392000-60000))<=20000)|(np.abs(f-(1420392000+60000))<=20000)
    E6_values[pair]={'median_feature_db':float(np.median(r[band])-np.median(r[side])),
                     'peak_near_target_db':float(r[np.abs(f-1420392000)<12000].max())}
    ix=(f>=1420280000)&(f<=1420500000)
    ax.plot(f[ix]/1e6,r[ix],lw=1,label=pair.replace('_','/'))
ax.axvspan(1420.372,1420.412,color='0.90',zorder=-1)
ax.axhline(0,color='0.5',lw=.6)
ax.set(xlabel='Absolute RF frequency (MHz)',ylabel='Smoothed baseline residual (dB)')
ax.ticklabel_format(axis='x',style='plain',useOffset=False)
ax.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter('%.3f'))
ax.legend(frameon=False,fontsize=6);ax.grid(alpha=.18)
fig.savefig(FIG/'e6_carina.pdf');plt.close(fig)

# E7: all independent ON/OFF contrast curves from original processed archive.
fig,ax=plt.subplots(figsize=(3.45,2.38))
d=readcsv('E7_resultados.zip','results/E7_carina/analysis/contrasts.csv')
for pair,g in d.groupby('pair',sort=False):
    ix=(g.frequency_hz>=1420280000)&(g.frequency_hz<=1420500000)
    ax.plot(g.loc[ix,'frequency_hz']/1e6,g.loc[ix,'residual_100khz_db'],lw=.95,
            label=pair.replace('_','/'))
ax.axvspan(1420.372,1420.412,color='0.90',zorder=-1)
ax.axhline(0,color='0.5',lw=.6)
ax.set(xlabel='Absolute RF frequency (MHz)',ylabel='Smoothed baseline residual (dB)')
ax.ticklabel_format(axis='x',style='plain',useOffset=False)
ax.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter('%.3f'))
ax.legend(frameon=False,fontsize=6);ax.grid(alpha=.18)
fig.savefig(FIG/'e7_on_off.pdf');plt.close(fig)

# E7: 10s window features with separate captures, no invented confidence intervals.
d=readcsv('E7_analise_final.zip','results/E7_carina/analysis_final/windows.csv')
fig,ax=plt.subplots(figsize=(7.14,2.55))
order=['A1','ON1','OFF1','ON2','OFF2','ON3','A2']
color={'ON':'C0','OFF':'C1','LOAD':'C2'}
base=0
for cap in order:
 g=d[d.capture==cap]
 x=np.arange(base,base+len(g))
 ax.plot(x,g.feature_db.values,marker='.',ms=3.8,lw=.75,label=g.condition.iloc[0] if cap in ('A1','ON1','OFF1') else None,color=color[g.condition.iloc[0]])
 ax.axvline(base-.5,color='0.84',lw=.5)
 ax.text(base+(len(g)-1)/2,0.205,cap,ha='center',fontsize=7)
 base+=len(g)
ax.set_ylim(-.21,.23);ax.set_xlim(-1,103)
ax.set(xlabel='Successive 10-s windows, grouped by acquisition',ylabel='Band-minus-sideband residual (dB)')
ax.legend(frameon=False,ncol=3,loc='lower left');ax.grid(axis='y',alpha=.18)
fig.savefig(FIG/'e7_time_windows.pdf');plt.close(fig)

# E7: entropy vs I-channel amplitude standard deviation, per acquisition means.
fig,ax=plt.subplots(figsize=(3.45,2.45))
sum_=readjson('E7_analise_final.zip','results/E7_carina/analysis_final/summary.json')['captures']
means=[]
for cap in order:
 val=sum_[cap]
 x=val['std_i']['mean'];y=val['shannon_i']['mean'];means.append([x,y])
 ax.scatter(x,y,s=22,marker='o' if 'ON' in cap else ('s' if 'OFF' in cap else '^'))
 ax.annotate(cap,(x,y),xytext=(4,3),textcoords='offset points',fontsize=6)
ax.set(xlabel='I-channel standard deviation (ADC counts)',ylabel='I-channel empirical Shannon entropy (bits)')
ax.set_xlim(4.25,7.45);ax.set_ylim(4.17,4.97);ax.grid(alpha=.18)
fig.savefig(FIG/'e7_entropy_amplitude.pdf');plt.close(fig)

# E7: two most relevant per-capture window metrics, descriptive only.
fig,ax=plt.subplots(figsize=(3.45,2.36))
feature=[sum_[c]['feature_db']['mean'] for c in order]
stds=[sum_[c]['feature_db']['sd_between_windows'] for c in order]
ax.errorbar(np.arange(len(order)),feature,yerr=stds,fmt='o',capsize=2,lw=1,ms=4)
ax.set_xticks(np.arange(len(order)),order)
ax.set(xlabel='Acquisition',ylabel='Spectral excess (dB), mean ± SD')
ax.axhline(0,color='0.5',lw=.6);ax.grid(axis='y',alpha=.2)
fig.savefig(FIG/'e7_feature_dispersion.pdf');plt.close(fig)

# Audited data descriptor
raw=readjson('E7_resultados.zip','results/E7_carina/analysis/summary.json')
assert len(d)==102 and d.groupby('capture').size().to_dict()==dict(A1=6,A2=6,ON1=18,ON2=18,ON3=18,OFF1=18,OFF2=18)
res={'e6_posthoc_baseline_residual_reanalysis':E6_values,
     'e7_correlation_shannon_i_std_i':float(d.shannon_i.corr(d.std_i)),
     'e7_correlation_feature_shannon_i':float(d.feature_db.corr(d.shannon_i)),
     'e7_load_median_ratio_db':None,
     'e7_window_count':len(d),'e7_contrasts':raw['pairs']}
s=readcsv('E7_resultados.zip','results/E7_carina/analysis/individual_spectra.csv')
res['e7_load_median_ratio_db']=float(np.median(10*np.log10(s.A2/s.A1)))
(ROOT/'analysis_checks.json').write_text(json.dumps(res,indent=2))
print('Generated 6 vector PDF figures in',FIG)
print(json.dumps({'e6':E6_values,'r_1':res['e7_correlation_shannon_i_std_i'],'r_2':res['e7_correlation_feature_shannon_i']},indent=2))
