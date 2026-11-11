#!/usr/bin/env python3
"""Virgo-RNG: análise temporal controlada A1/B1/A2/B2 em CU8.

Amostra uma janela por segundo; não é uma análise exaustiva nem teste de
entropia criptográfica. Convenção: cross(k)=corr(I[t],Q[t+k]).
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np

NAMES = ('A1_50ohm', 'B1_antenna', 'A2_50ohm', 'B2_antenna')

def corr(x, y):
    x = x - np.mean(x)
    y = y - np.mean(y)
    den = np.sqrt(np.dot(x, x) * np.dot(y, y))
    return float(np.dot(x, y) / den) if den else float('nan')

def metrics(block):
    i, q = block[::2].astype(np.float64), block[1::2].astype(np.float64)
    d = {'acf1_i': corr(i[:-1], i[1:]), 'acf1_q': corr(q[:-1], q[1:])}
    for lag in (0, -41, -8, 8, 41):
        if lag > 0:
            x, y = i[:-lag], q[lag:]
        elif lag < 0:
            x, y = i[-lag:], q[:lag]
        else:
            x, y = i, q
        d[f'cross_{lag:+d}'] = corr(x, y)
    for lag in (8, 41):
        d[f'antisym_{lag}'] = (d[f'cross_{lag:+d}'] - d[f'cross_{-lag:+d}']) / 2
    return d

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-dir', type=Path, default=Path('results/controlled_abab'))
    ap.add_argument('--out-dir', type=Path, default=Path('results/controlled_abab/analysis/temporal_drift'))
    ap.add_argument('--rate', type=int, default=2400000)
    ap.add_argument('--seconds', type=int, default=180)
    ap.add_argument('--pairs', type=int, default=65536)
    args = ap.parse_args()
    if args.rate <= 0 or args.seconds < 3 or args.pairs <= 82 or args.pairs > args.rate:
        ap.error('Use rate>0, seconds>=3, 82<pairs<=rate')
    args.out_dir.mkdir(parents=True, exist_ok=True)
    all_rows, summaries = [], {}
    for name in NAMES:
        path = args.data_dir / (name + '.cu8')
        expected = args.rate * args.seconds * 2
        actual = path.stat().st_size
        if actual != expected:
            raise ValueError(f'{path}: {actual} bytes; esperados {expected}. Abortando.')
        data = np.memmap(path, dtype=np.uint8, mode='r')
        rows = []
        for sec in range(args.seconds):
            start = 2 * sec * args.rate
            block = data[start:start + 2 * args.pairs]
            record = {'capture': name, 'second': sec, **metrics(block)}
            rows.append(record)
            all_rows.append(record)
        keys = list(rows[0].keys())[2:]
        t = np.arange(args.seconds, dtype=float)
        parts = np.array_split(np.arange(args.seconds), 3)
        summaries[name] = {}
        for k in keys:
            values = np.array([r[k] for r in rows])
            summaries[name][k] = {
                'mean': float(np.mean(values)),
                'std_across_windows': float(np.std(values)),
                'first_third': float(np.mean(values[parts[0]])),
                'middle_third': float(np.mean(values[parts[1]])),
                'last_third': float(np.mean(values[parts[2]])),
                'slope_per_minute': float(np.polyfit(t / 60, values, 1)[0]),
                'positive_windows': int(np.count_nonzero(values > 0)),
            }
        print(f'{name}: ACF I={summaries[name]["acf1_i"]["mean"]:.6f}; '
              f'ACF Q={summaries[name]["acf1_q"]["mean"]:.6f}; '
              f'antisym8={summaries[name]["antisym_8"]["mean"]:+.6f}')
        del data
    keys = list(all_rows[0])
    with (args.out_dir / 'windows_per_second.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_rows)
    diffs = {}
    for label, b, a in (('B1_minus_A1', 'B1_antenna', 'A1_50ohm'),
                        ('B2_minus_A2', 'B2_antenna', 'A2_50ohm')):
        diffs[label] = {k: summaries[b][k]['mean'] - summaries[a][k]['mean'] for k in summaries[a]}
    report = {
        'parameters': vars(args) | {'data_dir': str(args.data_dir), 'out_dir': str(args.out_dir)},
        'windows_per_capture': args.seconds,
        'pairs_per_window': args.pairs,
        'fraction_pairs_analyzed': args.pairs / args.rate,
        'lag_convention': 'cross(k)=corr(I[t],Q[t+k])',
        'antisym_convention': '(cross(+k)-cross(-k))/2',
        'capture_summaries': summaries,
        'paired_differences': diffs,
        'limitations': [
            'Amostra apenas uma janela de 65536 pares no início de cada segundo.',
            'Diferenças A/B podem refletir deriva, tempo, configuração ou RF; não são provas de origem astronômica.',
            'Sem estimativa validada de min-entropia ou ausência de perdas USB.'
        ]
    }
    (args.out_dir / 'summary.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Relatórios:', args.out_dir / 'summary.json', 'e', args.out_dir / 'windows_per_second.csv')

if __name__ == '__main__':
    main()
