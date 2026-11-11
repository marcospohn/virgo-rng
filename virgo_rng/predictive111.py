"""Offline, out-of-sample exploratory predictive entropy diagnostics. NOT SP 800-90B."""
import json
from pathlib import Path
import numpy as np


def _histories(x, k):
    # k previous 4-bit symbols, most recent in least significant nibble.
    n = len(x)
    code = np.zeros(n-k, dtype=np.uint64)
    for j in range(k):
        code = (code << np.uint64(4)) | x[j:n-k+j].astype(np.uint64)
    return code, x[k:]


def _scores(x, k, train_count, alpha=20.0):
    if not (0 < train_count < len(x)-k):
        raise ValueError('Not enough samples for chronological holdout')
    contexts, y = _histories(x, k)
    # Chronological train/test split, with k-1 boundary-crossing histories excluded.
    ntrain = train_count-k
    train_ctx, train_y = contexts[:ntrain], y[:ntrain]
    test_ctx, test_y = contexts[train_count:], y[train_count:]
    counts = np.bincount(train_y, minlength=16).astype(float)
    prior = (counts+1)/(len(train_y)+16)
    baseline_bits = float(np.mean(-np.log2(prior[test_y])))
    # Compact sparse joint table; never allocate 16**(k+1).
    joint = train_ctx*16 + train_y.astype(np.uint64)
    keys, vals = np.unique(joint, return_counts=True)
    uniq_ctx, ctx_idx = np.unique(keys//16, return_inverse=True)
    totals = np.bincount(ctx_idx, weights=vals)
    query_ctx = test_ctx
    ctx_pos = np.searchsorted(uniq_ctx, query_ctx)
    valid_ctx = ctx_pos < len(uniq_ctx)
    found_ctx = np.zeros(len(query_ctx), dtype=bool)
    found_ctx[valid_ctx] = uniq_ctx[ctx_pos[valid_ctx]] == query_ctx[valid_ctx]
    den = np.zeros(len(query_ctx), dtype=float)
    den[found_ctx] = totals[ctx_pos[found_ctx]]
    query_key = query_ctx*16 + test_y.astype(np.uint64)
    pos = np.searchsorted(keys, query_key)
    found_key = np.zeros(len(query_key), dtype=bool)
    valid_key = pos < len(keys)
    found_key[valid_key] = keys[pos[valid_key]] == query_key[valid_key]
    hits = np.zeros(len(query_key), dtype=float)
    hits[found_key] = vals[pos[found_key]]
    probs = (hits + alpha*prior[test_y])/(den+alpha)
    model_bits = float(np.mean(-np.log2(probs)))
    return {'history':k, 'train_symbols':int(ntrain),'test_symbols':int(len(test_y)),
            'baseline_cross_entropy_bits':baseline_bits,
            'model_cross_entropy_bits':model_bits,
            'predictive_gain_bits':baseline_bits-model_bits,
            'train_unique_contexts':int(len(uniq_ctx)),
            'test_unseen_context_fraction':float(np.mean(~found_ctx))}


def analyze_file(file, *, out_dir, rate=2400000, window_seconds=1.0,
                 sample_pairs=120000, windows=12, train_fraction=0.7, alpha=20.0, plot=True):
    file=Path(file); out_dir=Path(out_dir)
    if rate<=0 or window_seconds<=0 or sample_pairs<1000 or windows<1 or not (0.1<train_fraction<0.9) or alpha<=0:
        raise ValueError('Invalid parameters')
    wp=round(rate*window_seconds)
    if sample_pairs>wp: raise ValueError('sample_pairs exceeds window')
    if file.stat().st_size%2: raise ValueError('Incomplete I/Q pair')
    total=file.stat().st_size//2; nw=total//wp
    if nw==0: raise ValueError('No complete windows')
    indexes=np.unique(np.linspace(0,nw-1,min(windows,nw),dtype=int))
    train_count=int(sample_pairs*train_fraction)
    out=[]
    with file.open('rb') as f:
        for w in indexes:
            f.seek(int(w)*wp*2)
            raw=f.read(sample_pairs*2)
            if len(raw)!=sample_pairs*2: raise IOError('Short read')
            iq=np.frombuffer(raw,dtype=np.uint8).reshape(-1,2)
            row={'window_index':int(w),'start_seconds':float(w*wp/rate),'pairs_analyzed':sample_pairs,'channels':{}}
            for name, channel in (('I',iq[:,0]),('Q',iq[:,1])):
                x=(channel//16).astype(np.uint8)
                metrics=[_scores(x,k,train_count,alpha) for k in (1,2,4,8)]
                rng=np.random.default_rng(20261015+int(w)*7+(0 if name=='I' else 1))
                shuffled=x.copy();rng.shuffle(shuffled)
                control=[_scores(shuffled,k,train_count,alpha) for k in (1,2,4,8)]
                for m,c in zip(metrics,control):
                    m['shuffled_control_gain_bits']=c['predictive_gain_bits']
                    m['excess_gain_over_shuffled_bits']=m['predictive_gain_bits']-c['predictive_gain_bits']
                row['channels'][name]=metrics
            out.append(row)
    summary={}
    for channel in ('I','Q'):
        summary[channel]={str(k):{field:float(np.mean([r['channels'][channel][idx][field] for r in out]))
            for field in ('baseline_cross_entropy_bits','model_cross_entropy_bits','predictive_gain_bits','shuffled_control_gain_bits','excess_gain_over_shuffled_bits','test_unseen_context_fraction')}
            for idx,k in enumerate((1,2,4,8))}
    report={'schema':'virgo-rng-predictive-v1','source':str(file),'file_bytes':file.stat().st_size,
        'total_pairs':total,'window_pairs':wp,'windows_available':nw,'windows_selected':indexes.tolist(),
        'sample_pairs_per_window':sample_pairs,'quantization':'upper 4 bits of each 8-bit I/Q sample',
        'chronological_train_fraction':train_fraction,'dirichlet_prior_strength':alpha,
        'summary':summary,'windows':out,
        'limitations':['Cross-entropy is held-out predictive log loss, not Shannon conditional entropy or cryptographic min-entropy.',
        'Quantization to 4 bits per channel discards information; no inference about full 8-bit entropy is justified.',
        'Only selected windows and first sample_pairs of each are analyzed; no random representative sample claim.',
        'Shuffled controls break local ordering but do not eliminate all finite-sample biases or nonstationarity.',
        'Context-count models cannot rule out nonlinear, longer-range, or adversarial prediction.',
        'No NIST SP 800-90B entropy claim; no physical RF-noise isolation or validated source model.']}
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/'predictive_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axs=plt.subplots(2,1,figsize=(9,7),sharex=True)
        for ax,ch in zip(axs,('I','Q')):
            for key, label in [('predictive_gain_bits','Observed'),('shuffled_control_gain_bits','Shuffled control')]:
                ax.plot([1,2,4,8],[summary[ch][str(k)][key] for k in (1,2,4,8)],marker='o',label=label)
            ax.axhline(0,color='gray',linewidth=0.8)
            ax.set(ylabel='Held-out gain (bits/symbol)',title=f'Channel {ch}: 4-bit quantization')
            ax.legend();ax.grid(alpha=.2)
        axs[-1].set(xlabel='Previous samples used as context',xticks=[1,2,4,8])
        fig.tight_layout();fig.savefig(out_dir/'predictive_plot.png',dpi=150);plt.close(fig)
    return report
