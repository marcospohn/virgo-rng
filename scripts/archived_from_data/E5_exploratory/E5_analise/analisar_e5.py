import io, zipfile, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.ndimage import median_filter, gaussian_filter1d
import matplotlib.pyplot as plt

source=Path(__file__).resolve().parent.parent/'E4_repeticao.zip'
out=Path(__file__).resolve().parent
with zipfile.ZipFile(source) as z:
    csv=next(n for n in z.namelist() if n.endswith('/analysis/spectra.csv'))
    df=pd.read_csv(io.BytesIO(z.read(csv)))
f=df.frequency_hz.to_numpy(); p={n:df[n+'_power'].to_numpy() for n in ('ON1','OFF','ON2')}
r={n:10*np.log10(p[n]/p['OFF']) for n in ('ON1','ON2')}
r['average']=10*np.log10((p['ON1']+p['ON2'])/(2*p['OFF']))
result=pd.DataFrame({'frequency_hz':f,**{n+'_off_db':r[n] for n in r}})
for n in ('ON1','ON2','average'):
    med=median_filter(r[n],size=41,mode='nearest')
    baseline=gaussian_filter1d(med,sigma=220)
    residual=np.clip(r[n]-baseline,-3,3)
    result[n+'_broad_residual_db']=gaussian_filter1d(residual,sigma=25)
    result[n+'_baseline_db']=baseline
result.to_csv(out/'e5_processed.csv',index=False)
mask=(result.ON1_broad_residual_db>0.25)&(result.ON2_broad_residual_db>0.25)
starts=np.where(np.diff(np.r_[False,mask,False]))[0].reshape(-1,2)
regions=[{'start_mhz':float(f[a]/1e6),'end_mhz':float(f[b-1]/1e6),'average_excess_db':float(np.mean((result.ON1_broad_residual_db.iloc[a:b]+result.ON2_broad_residual_db.iloc[a:b])/2))} for a,b in starts if b-a>=15]
summary={'band_mhz':[float(f[0]/1e6),float(f[-1]/1e6)],'resolution_hz':float(np.median(np.diff(f))),'median_on_off_db':float(np.median(r['average'])),'broad_residual_peak_mhz':float(f[np.argmax(result.average_broad_residual_db)]/1e6),'broad_residual_peak_db':float(result.average_broad_residual_db.max()),'common_regions_above_0_25_db':regions,'method':'Median filter 41 bins, Gaussian baseline sigma 220 bins, Gaussian residual smoothing sigma 25 bins; exploratory and baseline dependent','calibrated':False}
(out/'e5_summary.json').write_text(json.dumps(summary,indent=2))
fig,ax=plt.subplots(figsize=(10,5));ax.plot(f/1e6,r['ON1'],lw=.65,alpha=.6,label='ON1 / OFF');ax.plot(f/1e6,r['ON2'],lw=.65,alpha=.6,label='ON2 / OFF');ax.plot(f/1e6,result.average_baseline_db,lw=2,label='Baseline estimada');ax.set(xlabel='Frequência (MHz)',ylabel='Contraste (dB)',title='E5 — Contrastes espectrais ON/OFF');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'contraste_on_off.png',dpi=160);plt.close(fig)
fig,ax=plt.subplots(figsize=(10,5));ax.plot(f/1e6,result.ON1_broad_residual_db,label='ON1');ax.plot(f/1e6,result.ON2_broad_residual_db,label='ON2');ax.axhline(0,color='gray',lw=.8);ax.set(xlabel='Frequência (MHz)',ylabel='Residual suavizado (dB)',title='E5 — Estrutura larga após remoção de baseline (exploratório)');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'residual_largo.png',dpi=160);plt.close(fig)
print(json.dumps(summary,indent=2))
