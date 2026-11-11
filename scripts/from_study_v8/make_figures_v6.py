#!/usr/bin/env python3
"""Reproduce the two new v6 vector figures from the archived E4/E5 and E6 processed data.
No raw CU8, network, or simulated radio data are used."""
from pathlib import Path
import zipfile
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
FIG = BASE / 'figures'
FIG.mkdir(exist_ok=True)
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
                     'axes.labelsize': 8, 'xtick.labelsize': 7,
                     'ytick.labelsize': 7, 'legend.fontsize': 7,
                     'pdf.fonttype': 42, 'savefig.bbox': 'tight'})

def read_zip_csv(archive, entry):
    with zipfile.ZipFile(DATA / archive) as z:
        return pd.read_csv(io.BytesIO(z.read(entry)))

# Sagittarius: baseline dependence of full E4-repeat integrated feature.
d45 = read_zip_csv('E4_E5_reprocessamento_resultados.zip', 'contrasts_e4_e5.csv')
fig, ax = plt.subplots(figsize=(3.55, 2.5))
for pair, style in [('ON1/OFF', 'o-'), ('ON2/OFF', 's--')]:
    x = d45[(d45['pair'] == pair) & (d45.method == 'after_dc') &
            (d45.mask_khz == 5)].sort_values('baseline_khz')
    ax.plot(x.baseline_khz, x.feature_db, style, lw=1.25, ms=4, label=pair)
ax.axhline(0, color='0.4', lw=.8)
ax.set_xticks([50, 100, 150, 250])
ax.set_xlabel('Baseline-smoothing width (kHz)')
ax.set_ylabel('Band-minus-sideband contrast (dB)')
ax.set_ylim(-.03, .205)
ax.grid(alpha=.2)
ax.legend(frameon=False, loc='upper left')
fig.tight_layout(pad=.7)
fig.savefig(FIG / 'e4e5_full_baseline.pdf')
plt.close(fig)

# Carina: same absolute RF candidate occupies two different positions in baseband.
d6 = read_zip_csv('E6_reprocessamento_resultados.zip', 'pair_spectra_dc.csv')
f, (a, b) = plt.subplots(1, 2, figsize=(7.12, 2.65),
                        gridspec_kw={'width_ratios': [1, 1]})
for pair, style in [('ON1/OFF1', '-'), ('ON2/OFF2', '--'), ('ON3/OFF3', ':')]:
    sub = d6[(d6['pair'] == pair) & (d6['method'] == 'dc_removed')]
    sub = sub[(sub.frequency_hz > 1420320000) & (sub.frequency_hz < 1420460000)]
    a.plot(sub.frequency_hz / 1e6, sub.residual_db, lw=1, ls=style, label=pair)
    b.plot(sub.baseband_offset_hz / 1e3, sub.residual_db, lw=1, ls=style, label=pair)
a.axvspan(1420.372, 1420.412, color='.8', alpha=.4)
a.axvline(1420.392, color='.45', lw=.8, ls='--')
a.set_xlim(1420.32, 1420.46)
a.set_xticks([1420.33, 1420.37, 1420.41, 1420.45])
a.set_xticklabels(['1420.33', '1420.37', '1420.41', '1420.45'], fontsize=7)
a.set_xlabel('Absolute RF frequency (MHz)')
a.set_ylabel('Local ON/OFF residual (dB)')
a.set_title('(a) Fixed RF location', size=8)
b.axvline(-313.752, color='.5', lw=.7, ls='--')
b.axvline(286.248, color='.5', lw=.7, ls='--')
b.set_xlim(-400, 400)
b.set_xticks([-350, -300, -250, 250, 300, 350])
b.tick_params(axis='x', labelsize=6)
b.set_xlabel('Baseband offset from center (kHz)')
b.set_title('(b) Shifted baseband locations', size=8)
for axis in (a, b):
    axis.axhline(0, lw=.6, color='.4')
    axis.grid(alpha=.13)
    axis.set_ylim(-.16, .20)
a.legend(frameon=False, loc='upper right', fontsize=6)
f.tight_layout(w_pad=1.2, pad=.6)
f.savefig(FIG / 'e6_full_retuning.pdf')
plt.close(f)
print('Generated v6 figures from E4/E5 and E6 processed ZIPs')
