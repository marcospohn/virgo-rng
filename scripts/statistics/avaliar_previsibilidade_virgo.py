#!/usr/bin/env python3
"""Virgo-RNG: teste exploratorio de previsibilidade fora da amostra.

Cada byte I/Q e discretizado nos 4 bits mais significativos (16 classes).
Contexto: I[t-1], Q[t-1] discretizados (256 estados).
Nao e estimador certificado de min-entropia SP 800-90B.
"""
import argparse, csv, json, math
from pathlib import Path
import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('files', nargs='+', type=Path, help='Arquivos CU8 I/Q intercalados')
    ap.add_argument('--rate', type=int, default=2400000)
    ap.add_argument('--seconds', type=int, default=180)
    ap.add_argument('--pairs', type=int, default=65536)
    ap.add_argument('--out', type=Path, default=Path('results/predictability'))
    args = ap.parse_args()
    if args.rate < 2 or args.seconds < 5 or not (3 <= args.pairs <= args.rate):
        ap.error('Parametros invalidos: rate>=2, seconds>=5, 3<=pairs<=rate')
    args.out.mkdir(parents=True, exist_ok=True)
    all_reports = []
    for path in args.files:
        expected = args.rate * args.seconds * 2
        if path.stat().st_size != expected:
            raise ValueError(f'{path}: tamanho {path.stat().st_size}, esperado {expected}')
        raw = np.memmap(path, dtype=np.uint8, mode='r')
        train_cut = int(args.seconds * .6)
        valid_cut = int(args.seconds * .8)
        counts = np.zeros((2, 256, 16), dtype=np.int64)
        marginal = np.zeros((2, 16), dtype=np.int64)
        for sec in range(train_cut):
            offset = 2 * args.rate * sec
            block = raw[offset:offset + 2 * args.pairs]
            i = block[::2] >> 4
            q = block[1::2] >> 4
            ctx = (i[:-1].astype(np.int32) * 16 + q[:-1].astype(np.int32))
            for ch, y in enumerate((i[1:], q[1:])):
                counts[ch] += np.bincount(ctx * 16 + y, minlength=4096).reshape(256,16)
                marginal[ch] += np.bincount(y, minlength=16)
        # Smoothing avoids impossible probabilities on unseen bins.
        p_cond = (counts + 1) / (counts.sum(axis=2, keepdims=True) + 16)
        p_base = (marginal + 1) / (marginal.sum(axis=1, keepdims=True) + 16)
        pred_cond = p_cond.argmax(axis=2)
        pred_base = p_base.argmax(axis=1)
        splits = {'validation': range(train_cut, valid_cut), 'test': range(valid_cut, args.seconds)}
        report = {'file': str(path), 'sampling': {'seconds': args.seconds, 'pairs_per_second': args.pairs, 'coverage': args.pairs / args.rate}, 'training_seconds': train_cut, 'validation_seconds': valid_cut-train_cut, 'test_seconds': args.seconds-valid_cut, 'channels': {}}
        for ch, label in enumerate(('I','Q')):
            report['channels'][label] = {}
            for split, seconds in splits.items():
                n, hits_cond, hits_base = 0, 0, 0
                logloss_cond, logloss_base = 0., 0.
                for sec in seconds:
                    offset = 2 * args.rate * sec
                    block = raw[offset:offset + 2 * args.pairs]
                    i = block[::2] >> 4
                    q = block[1::2] >> 4
                    ctx = i[:-1].astype(np.int32) * 16 + q[:-1].astype(np.int32)
                    y = (i if ch == 0 else q)[1:]
                    n += len(y)
                    hits_cond += np.count_nonzero(pred_cond[ch, ctx] == y)
                    hits_base += np.count_nonzero(pred_base[ch] == y)
                    logloss_cond -= np.log2(p_cond[ch, ctx, y]).sum()
                    logloss_base -= np.log2(p_base[ch, y]).sum()
                report['channels'][label][split] = {
                    'samples': n,
                    'baseline_accuracy': hits_base / n,
                    'conditional_accuracy': hits_cond / n,
                    'baseline_cross_entropy_bits_per_4bit_symbol': logloss_base / n,
                    'conditional_cross_entropy_bits_per_4bit_symbol': logloss_cond / n,
                    'cross_entropy_improvement_bits': (logloss_base-logloss_cond)/n,
                    'empirical_guessing_entropy_proxy_bits': -math.log2(hits_cond/n) if hits_cond else None,
                }
        all_reports.append(report)
        print(f'\n{path}')
        for label in ('I','Q'):
            r = report['channels'][label]['test']
            print(f"{label}: acerto base={r['baseline_accuracy']:.4%}; cond={r['conditional_accuracy']:.4%}; "
                  f"cross-entropy base={r['baseline_cross_entropy_bits_per_4bit_symbol']:.5f}; "
                  f"cond={r['conditional_cross_entropy_bits_per_4bit_symbol']:.5f} bits/simbolo")
        del raw
    destination = args.out / 'predictability_report.json'
    destination.write_text(json.dumps({'method': '4-bit I/Q symbols; context=(previous I, previous Q); Laplace smoothing; chronological 60/20/20 split; one 65536-pair contiguous window at start of each second', 'limitations': ['Not NIST SP 800-90B min-entropy validation.', 'Only 4 most significant bits of each 8-bit I/Q component.', 'Empirical guessing entropy is a predictive model score, not a guaranteed min-entropy bound.', 'Samples within windows and windows across time may be dependent.', 'Predictive ability may be underestimated by simple first-order model.', 'The code does not verify USB sample continuity.'], 'results': all_reports}, indent=2, ensure_ascii=False)+'\n')
    print('\nRelatorio:', destination)

if __name__ == '__main__':
    main()
