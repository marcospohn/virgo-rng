#!/usr/bin/env python3
"""Virgo-RNG: diagnóstico reproduzível de correlações em amostras CU8.
Definição: cross(k) = corr(I[t], Q[t+k]), para k positivo;
           cross(-k) = corr(I[t+k], Q[t]).
Analisa janelas distribuídas uniformemente; não estima min-entropia criptográfica.
"""
import argparse, csv, json
from pathlib import Path
import numpy as np

LAGS = (0, -41, -8, 8, 41)

def correlation(a, b):
    a = a - a.mean()
    b = b - b.mean()
    denom = np.sqrt(np.dot(a, a) * np.dot(b, b))
    return float(np.dot(a, b) / denom) if denom > 0 else None

def analyze(path, windows, pairs, output):
    size = path.stat().st_size
    if size % 2: raise ValueError('CU8 deve conter número par de bytes')
    total_pairs = size // 2
    if total_pairs < pairs: raise ValueError('Arquivo menor que uma janela')
    if pairs <= 82 or windows < 1: raise ValueError('Use pairs > 82 e windows >= 1')
    starts = np.linspace(0, total_pairs - pairs, windows, dtype=np.int64)
    raw = np.memmap(path, dtype=np.uint8, mode='r')
    rows = []
    for index, start in enumerate(starts):
        block = np.asarray(raw[2*int(start):2*(int(start)+pairs)], dtype=np.float64)
        i, q = block[::2], block[1::2]
        record = {'window': index, 'start_pair': int(start),
                  'acf1_i': correlation(i[:-1], i[1:]),
                  'acf1_q': correlation(q[:-1], q[1:])}
        for lag in LAGS:
            if lag > 0: a, b = i[:-lag], q[lag:]
            elif lag < 0: a, b = i[-lag:], q[:lag]
            else: a, b = i, q
            record[f'cross_{lag:+d}'] = correlation(a, b)
        for lag in (8, 41):
            record[f'antisym_{lag}'] = (record[f'cross_{lag:+d}'] - record[f'cross_{-lag:+d}']) / 2
        rows.append(record)
    output.mkdir(parents=True, exist_ok=True)
    with (output/'windows.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    metrics = [k for k in rows[0] if k not in ('window','start_pair')]
    summary = {'source': str(path), 'bytes': size, 'total_pairs': total_pairs,
               'windows': windows, 'pairs_per_window': pairs,
               'fraction_pairs_analyzed': windows * pairs / total_pairs,
               'lag_convention': 'cross(k) = corr(I[t], Q[t+k])',
               'antisym_convention': '(cross(+k) - cross(-k))/2',
               'metrics': {k: {'mean': float(np.mean([r[k] for r in rows])),
                               'std_across_windows': float(np.std([r[k] for r in rows])),
                               'min': float(np.min([r[k] for r in rows])),
                               'max': float(np.max([r[k] for r in rows]))} for k in metrics},
               'warning': 'Estatísticas descritivas, não estimativa validada de entropia criptográfica.'}
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(f'Arquivo: {path} ({size} bytes)')
    print(f'Janelas: {windows} x {pairs} pares; cobertura nominal {100*summary["fraction_pairs_analyzed"]:.3f}%')
    for k in metrics: print(f'{k:16s} {summary["metrics"][k]["mean"]:+.8f}')
    print('Resultados:', output/'summary.json', 'e', output/'windows.csv')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path, help='Arquivo de amostras CU8')
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--windows', type=int, default=120)
    p.add_argument('--pairs', type=int, default=65536)
    args=p.parse_args()
    analyze(args.file, args.windows, args.pairs, args.out_dir)

if __name__=='__main__': main()
