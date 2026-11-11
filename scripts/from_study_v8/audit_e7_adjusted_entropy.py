#!/usr/bin/env python3
"""Reproduce the exploratory E7 entropy correlations from the archived 102 windows.

These windows belong to the original E7 temporal analysis (not the later
DC-corrected FFT reprocessing). No CU8 input is required. The coefficients
are descriptive only: adjacent windows and captures are not independent sky
replications, and the regressions are not causal effect estimators.
"""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
import json
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'data' / 'E7_analise_final.zip'
MEMBER = 'results/E7_carina/analysis_final/windows.csv'
OUT = BASE / 'data'


def pearson(x, y):
    return float(np.corrcoef(np.asarray(x, dtype=float), np.asarray(y, dtype=float))[0, 1])


def adjusted(sub):
    d = sub.copy()
    for key in ('feature_db', 'shannon_i', 'std_i'):
        d[key+'_within'] = d[key] - d.groupby('capture')[key].transform('mean')
    x = d['feature_db_within'].to_numpy()
    y = d['shannon_i_within'].to_numpy()
    s = d['std_i_within'].to_numpy()
    if not s.any():
        raise ValueError('No within-capture amplitude variation')
    x_resid = x - s * (s @ x) / (s @ s)
    y_resid = y - s * (s @ y) / (s @ s)
    return {
        'n_windows': int(len(d)),
        'n_captures': int(d['capture'].nunique()),
        'pooled_spectral_entropy_r': pearson(d['feature_db'], d['shannon_i']),
        'pooled_shannon_amplitude_r': pearson(d['shannon_i'], d['std_i']),
        'capture_centered_spectral_entropy_r': pearson(x, y),
        'capture_and_std_i_partial_r': pearson(x_resid, y_resid),
    }, d


def main():
    with ZipFile(SOURCE) as archive:
        with archive.open(MEMBER) as fp:
            df = pd.read_csv(fp)
    columns = {'capture','condition','feature_db','shannon_i','std_i'}
    missing = columns - set(df.columns)
    if missing:
        raise ValueError(f'Missing columns: {sorted(missing)}')
    if len(df)!=102 or df.capture.nunique()!=7:
        raise ValueError('Unexpected E7 time-window/capture count')
    full, out_df = adjusted(df)
    sky, _ = adjusted(df[df.condition!='LOAD'])
    results = {
        'method': 'Pearson correlations; capture demeaning; OLS residualization on capture-centered std_i',
        'input': 'data/E7_analise_final.zip:results/E7_carina/analysis_final/windows.csv',
        'scope': 'Original E7 window-level spectrum/entropy summary; not later DC-corrected spectral features',
        'all_windows': full,
        'sky_windows': sky,
        'caveat': 'Descriptive only. 10-s windows are not independent astronomical replications; no causal interpretation or conventional p-values.',
    }
    OUT.mkdir(exist_ok=True)
    out_df.to_csv(OUT/'E7_entropy_adjusted_windows.csv', index=False)
    (OUT/'E7_entropy_adjusted_summary.json').write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n')
    assert abs(full['pooled_spectral_entropy_r'] - (-0.326092308426559)) < 1e-9
    assert abs(full['capture_centered_spectral_entropy_r'] - 0.10071977151008714) < 1e-9
    assert abs(full['capture_and_std_i_partial_r'] - 0.09677588987371541) < 1e-9
    print(json.dumps(results, indent=2))

if __name__=='__main__':
    main()
