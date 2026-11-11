"""Global max-lag permutation test for cross-channel dependence; exploratory."""
import json
from pathlib import Path
import numpy as np
from .lag_mi115 import lagged_mi


def global_test(file, *, out_dir, rate=2400000, window_seconds=1., sample_pairs=30000,
                windows=12, max_lag=32, quantization_bits=4, permutations=199,
                seed=116, plot=True):
    file=Path(file); out_dir=Path(out_dir)
    if rate<=0 or window_seconds<=0 or windows<2 or sample_pairs<1000 or max_lag<1 or max_lag*8>=sample_pairs or quantization_bits not in range(2,9) or permutations<19:
        raise ValueError('Invalid parameters (at least 19 permutations required)')
    wp=round(rate*window_seconds)
    if sample_pairs>wp: raise ValueError('sample_pairs exceeds window size')
    size=file.stat().st_size
    if size%2: raise ValueError('Incomplete IQ pair')
    nw=(size//2)//wp
    if nw<2: raise ValueError('Need at least two full windows')
    selected=np.unique(np.linspace(0,nw-1,min(windows,nw),dtype=int))
    lags=np.arange(-max_lag,max_lag+1); levels=1<<quantization_bits
    streams=[]
    with file.open('rb') as f:
        for w in selected:
            f.seek(int(w)*wp*2)
            raw=f.read(sample_pairs*2)
            if len(raw)!=sample_pairs*2: raise IOError('Short read')
            iq=np.frombuffer(raw,dtype=np.uint8).reshape(-1,2)
            streams.append((iq[:,0]>>(8-quantization_bits),iq[:,1]>>(8-quantization_bits)))
    def profile(i,q):
        return np.array([lagged_mi(i,q,int(k),levels) for k in lags])
    observed=np.stack([profile(i,q) for i,q in streams])
    obs_mean=observed.mean(axis=0)
    rng=np.random.default_rng(seed)
    null=np.empty((permutations,len(lags)))
    low=max(2*max_lag+1,sample_pairs//10)
    high=sample_pairs-low
    if high<=low: raise ValueError('Not enough samples for shifts')
    # One null replicate consists of independently shifting Q within each window,
    # preserving the I and Q marginal distributions and each channel's time order.
    for b in range(permutations):
        null[b]=np.mean([profile(i,np.roll(q,int(rng.integers(low,high)))) for i,q in streams],axis=0)
    baseline=null.mean(axis=0)
    obs_excess=obs_mean-baseline
    # Center null replicates at their own ensemble mean and take maximum over lags.
    # This accounts for selecting the largest of 2*max_lag+1 lags.
    null_max=(null-baseline).max(axis=1)
    observed_max=float(obs_excess.max())
    p_global=float((1+np.count_nonzero(null_max>=observed_max))/(permutations+1))
    # Pointwise p-values are descriptive only, and not used for the global claim.
    pointwise=((1+(null-baseline>=obs_excess).sum(axis=0))/(permutations+1)).tolist()
    result={'schema':'virgo-rng-global-lag-mi-v1','source':str(file),'source_bytes':size,
        'window_indices':selected.tolist(),'sample_pairs_per_window':sample_pairs,
        'quantization_bits_per_component':quantization_bits,'lags':lags.tolist(),
        'permutations':permutations,'seed':seed,
        'lag_definition':'MI(I[t];Q[t-k]); positive k means Q precedes I',
        'observed_mi_bits':obs_mean.tolist(),'null_mean_mi_bits':baseline.tolist(),
        'excess_mi_bits':obs_excess.tolist(),'pointwise_p_uncorrected':pointwise,
        'global_test':{'statistic':'max over lags of observed mean MI minus mean shifted-control MI',
            'max_excess_lag':int(lags[np.argmax(obs_excess)]),
            'max_excess_bits':observed_max,'p_value_max_statistic':p_global,
            'null_max_95th_percentile_bits':float(np.quantile(null_max,.95)),
            'null_max_99th_percentile_bits':float(np.quantile(null_max,.99))},
        'limitations':['Circular shifts are an approximate null, not a guarantee of exchangeability.',
            'Shared slow drift, periodicity, interference and receiver DSP may affect null validity.',
            'A small p-value does not identify physical origin or imply causal coupling.',
            'Windows are not independent receiver acquisitions.',
            'This is not a NIST SP 800-90B entropy estimate or proof of cryptographic security.',
            'Independent captures and different receiver configurations are required for replication.']}
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/'global_lag_mi_report.json').write_text(json.dumps(result,indent=2)+'\n')
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(11,5))
        ax.plot(lags,obs_excess,label='Observed MI excess')
        ax.axhline(np.quantile(null_max,.95),color='tab:orange',ls='--',label='95% global null max threshold')
        ax.axhline(0,color='gray',lw=1)
        ax.set(xlabel='Lag k: MI(I[t]; Q[t-k])',ylabel='MI excess over shifted null (bits)',
               title=f'Global max-lag test: p={p_global:.4g} ({permutations} controls)')
        ax.legend();ax.grid(alpha=.2);fig.tight_layout()
        fig.savefig(out_dir/'global_lag_mi_plot.png',dpi=160);plt.close(fig)
    return result
