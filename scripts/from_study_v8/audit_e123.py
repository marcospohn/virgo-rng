#!/usr/bin/env python3
"""E1-E3 PSD-only audit; output CSVs in data/. No original CU8 assumed."""
from pathlib import Path
import zipfile, io, json
import pandas as pd
import numpy as np
BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
TARGET = 1419988564.5
rows=[]
for fname in ('E1_results.zip','E1_repeticao.zip'):
    with zipfile.ZipFile(DATA / fname) as z:
        df=pd.read_csv(io.BytesIO(z.read('analysis/spectra.csv')))
        summ=json.loads(z.read('analysis/summary.json'))
    freq=df.frequency_hz.to_numpy()
    i=np.abs(freq-TARGET).argmin()
    for cap in ('ON1','OFF','ON2','A1','A2'):
        p=df[f'{cap}_psd'].to_numpy()
        neighbor=(abs(freq-freq[i])>4500)&(abs(freq-freq[i])<25000)
        rows.append({'experiment':fname[:-4], 'capture':cap,
                     'frequency_hz':freq[i],
                     'local_excess_db':10*np.log10(p[i]/np.median(p[neighbor])),
                     'psd_target':p[i],
                     'summary_peak_on_off_db':summ['peak_on_off_db']})
pd.DataFrame(rows).to_csv(DATA/'E1_controls_from_archived_psd.csv',index=False)
rows=[]
with zipfile.ZipFile(DATA/'E2_resultados.zip') as z:
    for tuning in (1420105752,1420405752,1420705752):
        path=f'results/E1_deslocamento/centro_{tuning}_spectrum.csv'
        df=pd.read_csv(io.BytesIO(z.read(path)))
        freq=df.frequency_hz.to_numpy()
        p=df.power.to_numpy()
        choices=np.where(abs(freq-TARGET)<=2500)[0]
        i=choices[np.argmax(p[choices])]
        neighbor=(abs(freq-TARGET)>=5000)&(abs(freq-TARGET)<=25000)
        rows.append({'tuning_hz':tuning,'peak_frequency_hz':freq[i],
                     'delta_from_target_hz':freq[i]-TARGET,
                     'offset_from_center_hz':freq[i]-tuning,
                     'local_excess_db':10*np.log10(p[i]/np.median(p[neighbor])),
                     'fft_resolution_hz':2400000/4096})
pd.DataFrame(rows).to_csv(DATA/'E2_retuning_from_archived_psd.csv',index=False)
with zipfile.ZipFile(DATA/'E3_resultados.zip') as z:
    summ=json.loads(z.read('results/E3_50ohm_antena/analysis/summary.json'))
rows=[{'capture':k,'local_excess_db':v['excess_db'],
       'peak_power':v['peak_power'],'local_baseline_power':v['local_baseline_power']}
      for k,v in summ['captures'].items()]
pd.DataFrame(rows).to_csv(DATA/'E3_load_antenna_archived_summary.csv',index=False)
print('Audited E1/E2/E3 from archived spectra and summaries (not CU8).')
