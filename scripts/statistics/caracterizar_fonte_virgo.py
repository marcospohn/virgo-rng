#!/usr/bin/env python3
"""Caracterização exploratória CU8 I/Q; não implementa NIST SP 800-90B."""
import argparse, csv, json, math
from pathlib import Path
import numpy as np

def metrics(counts):
    n = int(counts.sum())
    p = counts[counts > 0].astype(np.float64) / n
    return {'n': n, 'distinct': int(np.count_nonzero(counts)),
            'shannon_bits': float(-np.sum(p * np.log2(p))),
            'empirical_marginal_min_entropy_bits': float(-math.log2(float(p.max()))),
            'max_probability': float(p.max())}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('files', nargs='+', type=Path)
    ap.add_argument('--out', type=Path, default=Path('results/source_characterization'))
    ap.add_argument('--seconds-per-block', type=int, default=10)
    ap.add_argument('--rate', type=int, default=2400000)
    ap.add_argument('--chunk-pairs', type=int, default=1000000)
    args = ap.parse_args()
    if min(args.seconds_per_block, args.rate, args.chunk_pairs) <= 0: ap.error('parameters must be positive')
    args.out.mkdir(parents=True, exist_ok=True)
    summaries, blocks, histograms = [], [], {}
    for path in args.files:
        size = path.stat().st_size
        if size % 2: raise ValueError(f'{path}: odd byte count')
        total_pairs = size // 2
        raw = np.memmap(path, dtype=np.uint8, mode='r')
        counts_i = np.zeros(256, dtype=np.int64)
        counts_q = np.zeros(256, dtype=np.int64)
        counts_iq = np.zeros(65536, dtype=np.int64)
        block_pairs = args.seconds_per_block * args.rate
        for start in range(0, total_pairs, block_pairs):
            stop = min(start + block_pairs, total_pairs)
            bi = np.zeros(256, dtype=np.int64)
            bq = np.zeros(256, dtype=np.int64)
            bij = np.zeros(65536, dtype=np.int64)
            for pos in range(start, stop, args.chunk_pairs):
                end = min(pos + args.chunk_pairs, stop)
                sample = raw[2*pos:2*end]
                i = sample[::2]
                q = sample[1::2]
                bi += np.bincount(i, minlength=256)
                bq += np.bincount(q, minlength=256)
                idx = (i.astype(np.uint16) << 8) | q.astype(np.uint16)
                bij += np.bincount(idx.astype(np.int32), minlength=65536)
            counts_i += bi; counts_q += bq; counts_iq += bij
            row = {'capture': path.stem, 'start_second': start/args.rate,
                   'end_second': stop/args.rate}
            for label, c in (('I',bi),('Q',bq),('IQ',bij)):
                for key, val in metrics(c).items(): row[f'{label}_{key}'] = val
            blocks.append(row)
        result = {'capture': path.stem, 'file': str(path), 'pairs': total_pairs,
                  'seconds_at_nominal_rate': total_pairs/args.rate,
                  'I': metrics(counts_i), 'Q': metrics(counts_q), 'IQ': metrics(counts_iq)}
        result['empirical_mutual_information_IQ_bits'] = (result['I']['shannon_bits'] + result['Q']['shannon_bits'] - result['IQ']['shannon_bits'])
        summaries.append(result)
        histograms[path.stem] = {'I': counts_i.tolist(), 'Q': counts_q.tolist()}
        print(f"{path.stem}: H(I)={result['I']['shannon_bits']:.5f}, H(Q)={result['Q']['shannon_bits']:.5f}, H(I,Q)={result['IQ']['shannon_bits']:.5f}, MI={result['empirical_mutual_information_IQ_bits']:.6f}", flush=True)
        del raw
    with (args.out/'blocks.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(blocks[0])); writer.writeheader(); writer.writerows(blocks)
    (args.out/'summary.json').write_text(json.dumps({'method':'full-file marginal histograms, time-block summaries; not NIST SP 800-90B', 'parameters':{'rate':args.rate,'seconds_per_block':args.seconds_per_block},'captures':summaries,'histograms':histograms,'limitations':['Marginal empirical min-entropy is not a validated lower bound on conditional min-entropy.','I/Q joint symbol is 16-bit, not directly supported by some 90B estimators.','No claim of IID or cryptographic security.']}, indent=2)+'\n')
    print('Wrote',args.out/'summary.json', 'and',args.out/'blocks.csv')

if __name__ == '__main__': main()
