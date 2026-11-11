"""Exploratory, non-certifying entropy diagnostics and binary-output tests."""
import json
import math
from pathlib import Path
import numpy as np


def _read_channel(path, max_bytes=4_000_000, channel='i', skip_bytes=0):
    if max_bytes < 512 or max_bytes % 2 or skip_bytes < 0 or skip_bytes % 2:
        raise ValueError('max_bytes >= 512 and max_bytes/skip_bytes must be even')
    with Path(path).open('rb') as f:
        f.seek(skip_bytes)
        raw = f.read(max_bytes)
    raw = raw[:len(raw)//2*2]
    if len(raw) < 512:
        raise ValueError('Not enough complete I/Q samples')
    a = np.frombuffer(raw, dtype=np.uint8)
    return a[::2] if channel == 'i' else a[1::2]


def _max_probability(a):
    counts = np.bincount(a, minlength=256)
    return float(counts.max()/len(a))


def conditional_predictor(a, train_fraction=0.5):
    """Empirical one-step Markov predictor with disjoint chronological train/test.

    This is a predictability diagnostic, NOT a lower bound on min-entropy.
    """
    if len(a) < 1000:
        raise ValueError('Need at least 1000 observations')
    n = int(len(a)*train_fraction)
    if n < 2 or n >= len(a)-1:
        raise ValueError('Invalid split')
    transitions = np.zeros((256,256), dtype=np.int64)
    np.add.at(transitions, (a[:n-1], a[1:n]), 1)
    global_mode = int(np.bincount(a[:n], minlength=256).argmax())
    guess = transitions.argmax(axis=1).astype(np.uint8)
    guess[transitions.sum(axis=1) == 0] = global_mode
    target = a[n:]
    predicted = guess[a[n-1:-1]]
    hits = int(np.count_nonzero(predicted == target))
    baseline = int(np.count_nonzero(target == global_mode))
    return {'test_count':int(len(target)), 'correct':hits,
            'accuracy':hits/len(target), 'constant_baseline_accuracy':baseline/len(target),
            'training_fraction':train_fraction,
            'warning':'Prediction accuracy is NOT a validated conditional min-entropy estimate'}


def window_diagnostics(path, *, channel='i', max_bytes=4_000_000, window_samples=65536, skip_bytes=0):
    if window_samples < 512:
        raise ValueError('window_samples must be >=512')
    a = _read_channel(path, max_bytes, channel, skip_bytes)
    windows = []
    for offset in range(0, len(a)-window_samples+1, window_samples):
        x = a[offset:offset+window_samples]
        p = _max_probability(x)
        y = x.astype(np.float64)
        y -= y.mean()
        den = np.dot(y,y)
        acf = float(np.dot(y[:-1],y[1:])/den) if den else 1.0
        windows.append({'index':len(windows), 'sample_start':offset+skip_bytes//2,
                        'marginal_min_entropy_bits_per_byte':-math.log2(p),
                        'max_symbol_fraction':p, 'acf1':acf,
                        'std':float(x.std()), 'mean':float(x.mean())})
    if not windows:
        raise ValueError('No complete window')
    return {'status':'EXPLORATORY_NOT_NIST_VALIDATED', 'channel':channel,
            'setup':'indoor-dipole (reference) unless specified by operator',
            'bytes_read':len(a)*2, 'skipped_input_bytes':skip_bytes,
            'window_samples':window_samples, 'windows':windows,
            'one_step_predictor':conditional_predictor(a),
            'limitations':['Marginal entropy ignores temporal dependence',
                           'Markov predictor is diagnostic, not an SP 800-90B estimator',
                           'Windows from the same recording are not independent replicates']}


def binary_tests(path, *, max_bytes=8_000_000):
    if max_bytes < 1:
        raise ValueError('max_bytes must be positive')
    with Path(path).open('rb') as f:
        data=f.read(max_bytes)
    if len(data) < 32:
        raise ValueError('Need >=32 bytes')
    bits=np.unpackbits(np.frombuffer(data,dtype=np.uint8))
    n=len(bits)
    ones=int(bits.sum())
    p=ones/n
    z=(ones-n/2)/math.sqrt(n/4)
    # Two-sided normal approximation for the frequency test.
    pvalue=math.erfc(abs(z)/math.sqrt(2))
    runs=1+int(np.count_nonzero(bits[1:] != bits[:-1]))
    # Lag-one correlation of bits; no p-value assigned.
    b=bits.astype(np.float64)
    b-=b.mean()
    den=float(np.dot(b,b))
    acf=float(np.dot(b[:-1],b[1:])/den) if den else 1.0
    return {'status':'EXPLORATORY_NOT_NIST_SP800_22', 'bytes_tested':len(data),
            'bits_tested':n,'one_fraction':p,'frequency_z':z,
            'frequency_two_sided_p_approx':pvalue,'runs_count':runs,
            'lag1_autocorrelation':acf,
            'warning':'Passing tests cannot prove randomness or cryptographic security'}


def plot_windows(report, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    windows=report['windows']
    x=[w['index'] for w in windows]
    fig, ax=plt.subplots(figsize=(9,4.5))
    ax.plot(x,[w['marginal_min_entropy_bits_per_byte'] for w in windows],marker='.',markersize=3)
    ax.set(xlabel='Window index',ylabel='Marginal min-entropy (bits/byte)',
           title='Virgo-RNG: exploratory window statistics (NOT validated entropy)')
    ax.grid(alpha=0.2)
    fig.tight_layout()
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=140)
    plt.close(fig)


def save_report(path, report):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
