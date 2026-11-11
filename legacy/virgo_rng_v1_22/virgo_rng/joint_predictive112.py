"""Exploratory joint I/Q prediction with hierarchical n-gram backoff; not entropy certification."""
import json
from pathlib import Path
import numpy as np

ORDERS=(0,1,2,4,8)


def _history(x, k):
    n=len(x)
    if k==0:
        return np.zeros(n,dtype=np.uint64)
    codes=np.zeros(n-k,dtype=np.uint64)
    for j in range(k):
        codes=(codes<<np.uint64(4)) | x[j:n-k+j].astype(np.uint64)
    return codes


def _lookup(x, k, train_end, test_start, alpha):
    """Evaluate one order using recursively smoothed lower-order predictions.

    Test histories are wholly in test partition; no boundary leakage.
    """
    if not (8<=train_end<test_start<len(x)-8):
        raise ValueError('Invalid chronological split')
    # Evaluate all orders on exactly the same test targets.
    ytest=x[test_start:]
    counts=np.bincount(x[:train_end],minlength=16).astype(np.float64)
    prior=(counts+0.5)/(counts.sum()+8)
    probs=prior[ytest].copy()
    unseen=0.0
    for order in range(1,k+1):
        # Build contexts from training only; test contexts start at test_start.
        train_ctx=_history(x[:train_end],order)
        train_y=x[order:train_end]
        keys=(train_ctx<<np.uint64(4))|train_y.astype(np.uint64)
        uniq_keys,vals=np.unique(keys,return_counts=True)
        ctx_keys=uniq_keys>>np.uint64(4)
        uniq_ctx,ctx_first=np.unique(ctx_keys,return_index=True)
        totals=np.add.reduceat(vals,ctx_first).astype(np.float64)
        all_ctx=_history(x,order)
        query_ctx=all_ctx[test_start-order:len(x)-order]
        positions=np.searchsorted(uniq_ctx,query_ctx)
        good=positions<len(uniq_ctx)
        found=np.zeros(len(query_ctx),dtype=bool)
        found[good]=uniq_ctx[positions[good]]==query_ctx[good]
        denom=np.zeros(len(query_ctx),dtype=np.float64)
        denom[found]=totals[positions[found]]
        qkeys=(query_ctx<<np.uint64(4))|ytest.astype(np.uint64)
        p=np.searchsorted(uniq_keys,qkeys)
        valid=p<len(uniq_keys)
        hits=np.zeros(len(qkeys),dtype=np.float64)
        match=np.zeros(len(qkeys),dtype=bool)
        match[valid]=uniq_keys[p[valid]]==qkeys[valid]
        hits[match]=vals[p[match]]
        probs=(hits+alpha*probs)/(denom+alpha)
        if order==k: unseen=float(np.mean(~found))
    return {'history':k,'cross_entropy_bits':float(np.mean(-np.log2(probs))),
            'test_symbols':int(len(ytest)),'unseen_context_fraction':unseen}


def evaluate(x, *, train_fraction=0.7, alpha=30.0):
    x=np.asarray(x,dtype=np.uint8)
    if len(x)<100 or np.any(x>15) or not 0.2<train_fraction<0.85 or alpha<=0:
        raise ValueError('Invalid symbols or parameters')
    split=int(len(x)*train_fraction)
    test_start=split+8  # embargo: test histories never include training symbols
    results=[_lookup(x,k,split,test_start,alpha) for k in ORDERS]
    baseline=results[0]['cross_entropy_bits']
    for row in results: row['gain_vs_baseline_bits']=baseline-row['cross_entropy_bits']
    return results


def analyze_file(file, *, out_dir, rate=2400000, window_seconds=1.0,
                 sample_pairs=120000, windows=12, shuffle_repeats=3,
                 quantization_bits=2, alpha=30.0, plot=True):
    file=Path(file);out_dir=Path(out_dir)
    if rate<=0 or window_seconds<=0 or sample_pairs<1000 or windows<1 or shuffle_repeats<1 or quantization_bits not in (1,2):
        raise ValueError('Invalid parameters')
    wp=round(rate*window_seconds)
    if sample_pairs>wp:raise ValueError('sample_pairs exceeds window')
    size=file.stat().st_size
    if size%2:raise ValueError('Incomplete I/Q pair')
    total=size//2;nw=total//wp
    if not nw:raise ValueError('No complete windows')
    selected=np.unique(np.linspace(0,nw-1,min(windows,nw),dtype=int))
    rows=[]
    with file.open('rb') as f:
        for w in selected:
            f.seek(int(w)*wp*2)
            raw=f.read(sample_pairs*2)
            if len(raw)!=sample_pairs*2:raise IOError('Short read')
            iq=np.frombuffer(raw,dtype=np.uint8).reshape(-1,2)
            # Joint symbol: high 2 bits from each channel => 16 states.
            # For 1 bit: 4 states, but scoring uses a 16-state prior with zeros.
            shift=8-quantization_bits
            x=((iq[:,0]>>shift)<<quantization_bits)|(iq[:,1]>>shift)
            observed=evaluate(x,alpha=alpha)
            controls=[]
            for r in range(shuffle_repeats):
                rng=np.random.default_rng(112000+int(w)*97+r)
                shuffled=x.copy();rng.shuffle(shuffled) # preserve same-time I/Q pairs
                controls.append(evaluate(shuffled,alpha=alpha))
            for i,entry in enumerate(observed):
                vals=np.array([control[i]['gain_vs_baseline_bits'] for control in controls])
                entry['shuffled_control_mean_gain_bits']=float(vals.mean())
                entry['shuffled_control_std_gain_bits']=float(vals.std(ddof=1)) if len(vals)>1 else None
                entry['excess_over_shuffled_mean_bits']=float(entry['gain_vs_baseline_bits']-vals.mean())
            rows.append({'window_index':int(w),'start_seconds':float(w*wp/rate),'metrics':observed})
    summary={str(k):{field:float(np.mean([row['metrics'][i][field] for row in rows]))
                     for field in ('cross_entropy_bits','gain_vs_baseline_bits','unseen_context_fraction',
                                   'shuffled_control_mean_gain_bits','excess_over_shuffled_mean_bits')}
             for i,k in enumerate(ORDERS)}
    report={'schema':'virgo-rng-joint-predictive-v1','source':str(file),'file_bytes':size,
        'total_pairs':total,'window_pairs':wp,'windows_available':nw,'windows_selected':selected.tolist(),
        'sample_pairs_per_window':sample_pairs,'quantization_bits_per_component':quantization_bits,
        'alphabet_size':2**(2*quantization_bits),'context_orders':list(ORDERS),
        'train_fraction':0.7,'test_embargo_pairs':8,'backoff_alpha':alpha,
        'shuffle_repeats':shuffle_repeats,'shuffle_preserves_simultaneous_IQ_pairing':True,
        'summary':summary,'windows':rows,'limitations':[
        'Held-out log loss measures predictive performance, not cryptographic min-entropy.',
        'Coarse quantization discards most of the original 8-bit I/Q values.',
        'Models are trained and evaluated separately within selected windows; results do not cover all 432M pairs.',
        'Backoff is a specific finite model and cannot exclude other predictors or adversarial side information.',
        'Shuffling removes temporal ordering but retains same-time I/Q pairing; this is an exploratory control.',
        'Averaging windows is not a confidence bound or NIST SP 800-90B entropy assessment.']}
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/'joint_predictive_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        xs=list(ORDERS)
        fig,ax=plt.subplots(figsize=(9,5))
        ax.plot(xs,[summary[str(k)]['gain_vs_baseline_bits'] for k in xs],marker='o',label='Observed')
        ax.plot(xs,[summary[str(k)]['shuffled_control_mean_gain_bits'] for k in xs],marker='o',label='Shuffled pairs')
        ax.axhline(0,color='gray',lw=.8)
        ax.set(xlabel='Previous I/Q pairs used as context',ylabel='Held-out gain (bits/quantized pair)',
               title='Joint I/Q prediction with hierarchical backoff',xticks=xs)
        ax.legend();ax.grid(alpha=.2);fig.tight_layout()
        fig.savefig(out_dir/'joint_predictive_plot.png',dpi=150);plt.close(fig)
    return report
