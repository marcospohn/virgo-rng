"""v1.19 exploratory time-local block reordering audit (not a calibrated null test)."""
import argparse
import json
from pathlib import Path
import numpy as np
from .lag_mi115 import lagged_mi


def _quantize(iq, bits):
    return iq[:, 0] >> (8-bits), iq[:, 1] >> (8-bits)


def _profile(i, q, lags, levels):
    return np.array([lagged_mi(i, q, int(k), levels) for k in lags], dtype=float)


def _block_reorder(q, block_pairs, rng):
    """Reorder whole contiguous Q blocks; no sample-level shuffle or wrap."""
    n = len(q)
    blocks = n // block_pairs
    if blocks < 8 or n % block_pairs:
        raise ValueError('Sample pairs must be divisible by block pairs; need >=8 blocks')
    order = rng.permutation(blocks)
    return q.reshape(blocks, block_pairs)[order].reshape(n)


def _moments(x):
    x = x.astype(float)
    return {'mean': float(x.mean()), 'std': float(x.std()),
            'lag1_corr': float(np.corrcoef(x[:-1], x[1:])[0,1]) if x.std()>0 else None}


def run(file, out_dir, *, rate=2400000, window_seconds=1.0,
        sample_pairs=32768, windows=12, max_lag=32, bits=4,
        permutations=199, block_pairs=256, seed=119, plot=True):
    file=Path(file);out_dir=Path(out_dir)
    if rate<=0 or window_seconds<=0 or windows<2 or max_lag<1 or bits not in range(2,9) or permutations<19 or block_pairs<=max_lag*2:
        raise ValueError('Invalid parameters')
    wp=round(rate*window_seconds)
    if sample_pairs>wp or sample_pairs<=max_lag*8 or sample_pairs%block_pairs or sample_pairs//block_pairs<8:
        raise ValueError('Invalid sample_pairs / block_pairs')
    size=file.stat().st_size
    if size%2:raise ValueError('Incomplete I/Q pair')
    nw=size//2//wp
    if nw<2:raise ValueError('Need >=2 full windows')
    selected=np.unique(np.linspace(0,nw-1,min(windows,nw),dtype=int))
    streams=[]
    with file.open('rb') as f:
        for w in selected:
            f.seek(int(w)*wp*2)
            raw=f.read(sample_pairs*2)
            if len(raw)!=sample_pairs*2:raise IOError('Short read')
            streams.append(_quantize(np.frombuffer(raw,dtype=np.uint8).reshape(-1,2),bits))
    levels=1<<bits;lags=np.arange(-max_lag,max_lag+1)
    observed_windows=np.stack([_profile(i,q,lags,levels) for i,q in streams]);observed=observed_windows.mean(axis=0)
    rng=np.random.default_rng(seed)
    null=np.empty((permutations,len(lags)),dtype=float)
    # Permute Q blocks separately within each observed window, preserve I unchanged.
    for b in range(permutations):
        null[b]=np.mean([_profile(i,_block_reorder(q,block_pairs,rng),lags,levels) for i,q in streams],axis=0)
    center=null.mean(axis=0);excess=observed-center
    null_max=(null-center).max(axis=1)
    pglobal=(1+int(np.sum(null_max>=excess.max())))/(permutations+1)
    idxs={k:int(np.where(lags==k)[0][0]) for k in (-8,8) if abs(k)<=max_lag}
    pointwise={str(k):(1+int(np.sum(null[:,ix]-center[ix]>=excess[ix])))/(permutations+1) for k,ix in idxs.items()}
    # Independent, coarse chronological windows for descriptive variation.
    diagnostics=[]
    for w,(i,q),mi in zip(selected,streams,observed_windows):
        diagnostics.append({'window_index':int(w),'i':_moments(i),'q':_moments(q),
                            'mi_minus8':float(mi[idxs[-8]]) if -8 in idxs else None,
                            'mi_plus8':float(mi[idxs[8]]) if 8 in idxs else None})
    # Sub-block descriptive variation within each selected window; no formal stationarity claim.
    subblock=[]
    for i,q in streams:
        for start in range(0,len(i),block_pairs):
            subblock.append((float(i[start:start+block_pairs].std()),float(q[start:start+block_pairs].std())))
    out_dir.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out_dir/'local_null_profiles.npz',lags=lags,observed_windows=observed_windows,
                        block_reordered_null_profiles=null,selected_windows=selected)
    report={'schema':'virgo-rng-local-audit-v119','source':str(file),'source_bytes':size,
            'parameters':{'rate':rate,'window_seconds':window_seconds,'sample_pairs':sample_pairs,
                          'windows':len(selected),'max_lag':max_lag,'bits':bits,'permutations':permutations,
                          'block_pairs':block_pairs,'seed':seed},
            'observed_mi_bits':observed.tolist(),'lags':lags.tolist(),
            'block_reorder':{'p_global_exploratory':pglobal,'max_lag':int(lags[np.argmax(excess)]),
                             'max_excess_bits':float(excess.max()),
                             'null_max_95_bits':float(np.quantile(null_max,.95)),
                             'pointwise_p_exploratory':pointwise,'observed_excess_bits':excess.tolist(),
                             'null_mean_mi_bits':center.tolist()},
            'per_window_diagnostics':diagnostics,
            'within_window_block_std_range':{'i':[float(np.min(np.array(subblock)[:,0])),float(np.max(np.array(subblock)[:,0]))],
                                             'q':[float(np.min(np.array(subblock)[:,1])),float(np.max(np.array(subblock)[:,1]))]},
            'limitations':['Block reordering breaks cross-channel alignment but also changes longer-range Q structure.',
                           'Block reordering does not establish exchangeability, so reported p-values are exploratory, not calibrated.',
                           'Only sparse short portions of the recording are analyzed, not the entire 180 seconds.',
                           'Per-window moments and lag peaks are descriptive; no formal stationarity or periodicity inference.',
                           'First capture is exploratory; replication must be separately interpreted.',
                           'No physical source attribution or cryptographic min-entropy inference.']}
    (out_dir/'local_audit_report.json').write_text(json.dumps(report,indent=2)+'\n')
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(10,5));ax.plot(lags,excess,label='Observed MI excess vs reordered Q blocks')
        ax.axhline(0,color='gray',lw=1);ax.set(xlabel='Lag k',ylabel='MI excess (bits)',
                title=f'Exploratory Q-block reordering (global p={pglobal:.3f}; NOT calibrated)')
        ax.grid(alpha=.2);ax.legend();fig.tight_layout();fig.savefig(out_dir/'local_audit_plot.png',dpi=150);plt.close(fig)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file');p.add_argument('--out-dir',required=True)
    p.add_argument('--permutations',type=int,default=199)
    p.add_argument('--block-pairs',type=int,default=256)
    p.add_argument('--sample-pairs',type=int,default=32768)
    p.add_argument('--windows',type=int,default=12)
    p.add_argument('--rate',type=int,default=2400000)
    p.add_argument('--max-lag',type=int,default=32)
    p.add_argument('--seed',type=int,default=119)
    a=p.parse_args()
    r=run(a.file,a.out_dir,permutations=a.permutations,block_pairs=a.block_pairs,
          sample_pairs=a.sample_pairs,windows=a.windows,rate=a.rate,max_lag=a.max_lag,seed=a.seed)
    print(json.dumps({'exploratory_global_p':r['block_reorder']['p_global_exploratory'],
                      'peak_lag':r['block_reorder']['max_lag']},indent=2))
if __name__=='__main__':main()
