from pathlib import Path
import numpy as np, pandas as pd, json, io, zipfile, itertools
from scipy import stats
from datetime import datetime
from matplotlib import pyplot as plt
from math import pi
import argparse

parser=argparse.ArgumentParser(description='Uncertainty, geometric pointing and frequency-placebo diagnostics for E7; no SDR required')
parser.add_argument('--dc-zip', type=Path, default=Path('E7_DC_resultados.zip'))
parser.add_argument('--e7-zip', type=Path, default=Path('E7_resultados.zip'))
parser.add_argument('--out', type=Path, default=Path('E7_complementar'))
args=parser.parse_args()
OUT=args.out;OUT.mkdir(parents=True, exist_ok=True)
Z=zipfile.ZipFile(args.dc_zip)
w=pd.read_csv(io.BytesIO(Z.read('windows_dc.csv')))
contr=pd.read_csv(io.BytesIO(Z.read('contrasts_dc.csv')))
spec=pd.read_csv(io.BytesIO(Z.read('individual_spectra.csv')))
with zipfile.ZipFile(args.e7_zip) as zmeta:
    metadata=json.loads(zmeta.read('results/E7_carina/metadata.json'))
names=['ON1','OFF1','ON2','OFF2','ON3']; ON=['ON1','ON2','ON3'];OFF=['OFF1','OFF2']

# GMST approx + conventional J2000 ICRS Galactic matrix: accuracy appropriate for manually pointed antenna.
R=np.array([[-.0548755604162154,-.873437090234885,-.4838350155487132],
            [.4941094278755837,-.4448296299600112,.7469822444972189],
            [-.8676661490190047,-.1980763734312015,.4559837761750669]])
def galactic(when,azd,eld,latd=-27.1,lond=-52.62):
    jd=datetime.fromisoformat(when.replace('Z','+00:00')).timestamp()/86400+2440587.5
    T=(jd-2451545.0)/36525
    gmst=280.46061837+360.98564736629*(jd-2451545.0)+0.000387933*T**2-T**3/38710000
    lst=np.deg2rad((gmst+lond)%360.)
    lat, az,el=np.deg2rad([latd,azd,eld])
    dec=np.arcsin(np.sin(lat)*np.sin(el)+np.cos(lat)*np.cos(el)*np.cos(az))
    ha=np.arctan2(-np.cos(el)*np.sin(az),np.cos(lat)*np.sin(el)-np.sin(lat)*np.cos(el)*np.cos(az))
    ra=lst-ha
    g=R@np.array([np.cos(dec)*np.cos(ra),np.cos(dec)*np.sin(ra),np.sin(dec)])
    return {'ra_deg':float(np.rad2deg(ra)%360),'dec_deg':float(np.rad2deg(dec)),
            'gal_lon_deg':float(np.rad2deg(np.arctan2(g[1],g[0]))%360),'gal_lat_deg':float(np.rad2deg(np.arcsin(g[2])))}
coords=[]
for r in metadata:
 if r['condition']!='LOAD':
  a=galactic(r['start_utc'],r['azimuth_deg'],r['elevation_deg'])
  coords.append(dict(capture=r['name'],timestamp_utc=r['start_utc'],azimuth_deg=r['azimuth_deg'],elevation_deg=r['elevation_deg'],**a))
pd.DataFrame(coords).to_csv(OUT/'coordenadas_galacticas.csv',index=False)

rng=np.random.default_rng(20261110)
def circular_bootstrap(x,B=50000,L=3):
    x=np.asarray(x);n=len(x)
    starts=rng.integers(0,n,size=(B,int(np.ceil(n/L))))
    indices=(starts[:,:,None]+np.arange(L)[None,None,:])%n
    return x[indices.reshape(B,-1)[:,:n]].mean(axis=1)
summary={}; per_group=[]; results=[]
for mask in [5.0,10.0]:
  d=w[(w.method=='dc_removed')&(w.mask_dc_khz==mask)]
  vals={n:d[d.capture==n].sort_values('start_s').local_feature_db.to_numpy() for n in names}
  feature_means={n:float(x.mean()) for n,x in vals.items()}
  on=float(np.mean([feature_means[n] for n in ON]));off=float(np.mean([feature_means[n] for n in OFF]));diff=on-off
  diffs_perms=[]
  array=np.array([feature_means[n] for n in names])
  for ix in itertools.combinations(range(5),3):
    chosen=set(ix)
    diffs_perms.append(float(array[list(ix)].mean()-array[[i for i in range(5) if i not in chosen]].mean()))
  perm_p=float(np.mean(np.array(diffs_perms)>=diff-1e-12))
  # fixed sessions uncertainty based on 30s or 60s circular block bootstrap
  conditional={}
  for L in [1,3,6]:
    a=np.mean([circular_bootstrap(vals[n],L=L) for n in ON],axis=0)
    b=np.mean([circular_bootstrap(vals[n],L=L) for n in OFF],axis=0)
    intervals=np.quantile(a-b,[.025,.50,.975]);conditional[str(L*10)]={'low':float(intervals[0]),'median':float(intervals[1]),'high':float(intervals[2])}
  # capture resampling; unsuited for generalization but transparent very few captures
  mc=np.array([feature_means[n] for n in ON]);fc=np.array([feature_means[n] for n in OFF])
  onboot=rng.choice(mc,size=(50000,len(mc)),replace=True).mean(axis=1)
  offboot=rng.choice(fc,size=(50000,len(fc)),replace=True).mean(axis=1)
  capres=np.quantile(onboot-offboot,[.025,.975])
  # Welch CI (very low df; treat exploratory)
  se=np.sqrt(mc.var(ddof=1)/len(mc)+fc.var(ddof=1)/len(fc))
  va=mc.var(ddof=1)/len(mc);vb=fc.var(ddof=1)/len(fc)
  df=(va+vb)**2/(va**2/(len(mc)-1)+vb**2/(len(fc)-1))
  ci_w=stats.t.interval(.95,df,loc=diff,scale=se)
  result={'mask_khz':mask,'means_db':feature_means,'on_capture_mean_db':on,'off_capture_mean_db':off,
          'contrast_capture_mean_db':diff,'exact_assignment_one_sided_p':perm_p,
          'num_sky_captures':5,'num_label_assignments':10,
          'fixed_session_block_bootstrap_ci95_db':conditional,
          'capture_resampling_ci95_exploratory_db':[float(x) for x in capres],
          'welch_ci95_capture_means_exploratory_db':[float(x) for x in ci_w],
          'welch_df':float(df)}
  summary[str(mask)]=result
  results.append(result)
  for name in names:
    x=vals[name]
    sec=np.arange(len(x))*10+5
    slope,intercept=np.polyfit(sec,x,1)
    per_group.append({'mask_khz':mask,'capture':name,'num_windows':len(x),'mean_db':float(x.mean()),
       'std_db':float(x.std(ddof=1)),'fraction_positive':float(np.mean(x>0)),'trend_db_per_min':float(slope*60),'first_db':float(x[0]),'last_db':float(x[-1])})
pd.DataFrame(per_group).to_csv(OUT/'estatisticas_por_captura.csv',index=False)

# frequency placebo diagnostic, no formal p-value. Original pipeline, target 1420.392 MHz and DC mask 5kHz.
F=spec.frequency_hz.to_numpy();rate=2400000;center=1420405752;target=1420392000
# same moving mean edge-reflect

def mm(x,n):return np.convolve(np.pad(x,(n//2,n//2),mode='reflect'),np.ones(n)/n,mode='valid')
def clean(x,mask=5000):
  ok=np.abs(F-center)>mask
  return np.interp(F,F[ok],x[ok])
resid={}
for a,b in [('ON1','OFF1'),('ON2','OFF2'),('ON3','OFF2')]:
 ratio=10*np.log10(np.maximum(spec[a+'_dc_power'].to_numpy(),1e-24)/np.maximum(spec[b+'_dc_power'].to_numpy(),1e-24))
 sm=mm(clean(ratio),35);resid[a+'/'+b]=sm-mm(sm,341)

# residual vs alternate target centers, candidate half width=20kHz, side bands 40-80kHz
rows=[]
for target_trial in [target]+[int(center+delta) for delta in np.arange(-950000,950001,20000) if abs(delta+13752)>20000]:
 if not F.min()+85000<target_trial<F.max()-85000:continue
 valid=np.abs(F-center)>5000
 band=(np.abs(F-target_trial)<=20000)&valid
 side=(np.abs(F-target_trial)>=40000)&(np.abs(F-target_trial)<=80000)&valid
 if band.sum()<40 or side.sum()<80:continue
 metrics=[float(np.median(y[band])-np.median(y[side])) for y in resid.values()]
 rows.append({'target_hz':target_trial,'delta_from_dc_khz':(target_trial-center)/1000,
              'contrast_mean_db':float(np.mean(metrics)),'contrast_min_db':min(metrics),
              'all_three_positive':bool(all(v>0 for v in metrics)),**{k:v for k,v in zip(resid,metrics)}})
placebo=pd.DataFrame(rows).sort_values('target_hz')
placebo.to_csv(OUT/'faixas_controle_espectrais.csv',index=False)
obs=float(placebo.loc[placebo.target_hz==target,'contrast_mean_db'].iloc[0]);alt=placebo[placebo.target_hz!=target]
# show percentile overall and at near-freq region: descriptive, not probability
summary['spectral_placebo']={'original_target_mean_db':obs,'number_other_windows':len(alt),
 'fraction_other_windows_with_larger_excess':float((alt.contrast_mean_db>=obs).mean()),
 'fraction_other_windows_all_three_positive':float(alt.all_three_positive.mean()),
 'max_other_mean_db':float(alt.contrast_mean_db.max()),
 'max_other_center_mhz':float(alt.loc[alt.contrast_mean_db.idxmax(),'target_hz']/1e6)}

# Full-record pair DC-masked main estimates for unchanged provenance
q=contr[(contr.method=='dc_removed')&(contr.mask_dc_khz.isin([5.,10.]))]
q.to_csv(OUT/'contrastes_integrados_correção_DC.csv',index=False)

fig,ax=plt.subplots(figsize=(9,4.4))
for i,n in enumerate(['ON1','OFF1','ON2','OFF2','ON3']):
  v=w[(w.capture==n)&(w.method=='dc_removed')&(w.mask_dc_khz==5)].sort_values('start_s').local_feature_db.to_numpy()
  ax.errorbar(i,np.mean(v),yerr=np.std(v,ddof=1),capsize=4,fmt='o',label=None,color='C0' if n.startswith('ON') else 'C1')
ax.set_xticks(range(5),['ON1','OFF1','ON2','OFF2','ON3']);ax.set_ylabel('Residual médio ± desvio temporal (dB)')
ax.axhline(0,color='gray',lw=.8);ax.grid(alpha=.2);fig.tight_layout();fig.savefig(OUT/'e7_capturas_incerteza.png',dpi=180);plt.close(fig)

fig,ax=plt.subplots(figsize=(9,4.1))
ax.plot((placebo.target_hz-center)/1e3,placebo.contrast_mean_db,'o-',ms=2.0,lw=.6,color='#7d8890')
ax.axvline((target-center)/1e3,lw=1.2,color='#ab3f37')
ax.scatter([(target-center)/1e3],[obs],s=60,color='#ab3f37',zorder=3)
ax.set_xlabel('Deslocamento da janela candidata em relação ao centro SDR (kHz)')
ax.set_ylabel('Média de três contrastes ON/OFF (dB)')
ax.grid(alpha=.2);fig.tight_layout();fig.savefig(OUT/'e7_controles_frequencia.png',dpi=180);plt.close(fig)

nu0=1420405751.77;v_radio=299792.458*(nu0-target)/nu0
summary['geometry']={'coordinates':coords,'target_frequency_hz':target,'topocentric_radio_velocity_km_s_approx':v_radio,
    'method':'approximate GMST and altaz transformation; manually pointed; no LSR correction; assumed Chapeco lat=-27.10 long=-52.62'}
summary['limitations']=['Fixed-session temporal block bootstrap is conditional on these five recordings and cannot address session-to-session systematics or sky-attribution.',
 'Exact permutation over 5 sky recordings has minimum one-sided p=0.10 and assumes exchangeability violated by time-order/pointing.',
 'Frequency-placebo scan is a diagnostic, not a calibrated null distribution: spectral bins are correlated and target was preselected based on E6.',
 'No external HI4PI spectrum for recorded coordinates was downloaded; qualitative spatial consistency only; no direct profile or velocity comparison.',
 'The observing setup lacks absolute calibration, verified antenna beam, precise pointing and logged gain/noise temperature.']
(OUT/'resumo.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
print(json.dumps(summary,indent=2,ensure_ascii=False)[:14000])
