"""Exploratory circular-shift null audit. Stores complete null profiles."""
import argparse
import json
from pathlib import Path
import numpy as np
from .lag_mi115 import lagged_mi


def run(file, out_dir, *, rate=2400000, window_seconds=1., sample_pairs=30000,
        windows=12, max_lag=32, bits=4, permutations=199, seed=118, plot=True):
    file=Path(file); out_dir=Path(out_dir)
    if rate<=0 or window_seconds<=0 or sample_pairs<1000 or windows<2 or max_lag<1 or bits not in range(2,9) or permutations<19:
        raise ValueError('Invalid parameters')
    wp=round(rate*window_seconds)
    if sample_pairs>wp or sample_pairs<=max_lag*8: raise ValueError('Invalid sample_pairs')
    size=file.stat().st_size
    if size%2: raise ValueError('Incomplete IQ pair')
    nw=size//2//wp
    if nw<2: raise ValueError('Need two windows')
    selected=np.unique(np.linspace(0,nw-1,min(windows,nw),dtype=int))
    streams=[]
    with file.open('rb') as f:
        for w in selected:
            f.seek(int(w)*wp*2)
            raw=f.read(sample_pairs*2)
            if len(raw)!=sample_pairs*2: raise IOError('Short read')
            iq=np.frombuffer(raw,dtype=np.uint8).reshape(-1,2)
            streams.append((iq[:,0]>>(8-bits),iq[:,1]>>(8-bits)))
    lags=np.arange(-max_lag,max_lag+1); levels=1<<bits
    def profile(i,q):return np.array([lagged_mi(i,q,int(k),levels) for k in lags])
    observed_windows=np.stack([profile(i,q) for i,q in streams]); observed=observed_windows.mean(axis=0)
    rng=np.random.default_rng(seed)
    # Compare two null constructions, both preserving the full within-channel ordering.
    # Wide: offsets away from the tested lag region; half-turn: narrower offsets near n/2.
    nulls={}; shifts={}; diagnostics={}
    for method in ('wide','half_turn'):
        profiles=np.empty((permutations,len(lags))); offsets=np.empty((permutations,len(streams)),dtype=int)
        for b in range(permutations):
            rows=[]
            for j,(i,q) in enumerate(streams):
                n=len(q)
                if method=='wide':
                    low=max(2*max_lag+1,n//10); high=n-low
                else:
                    low=n//2-max(max_lag*2,n//20);high=n//2+max(max_lag*2,n//20)
                if high<=low: raise ValueError('Shift range empty')
                shift=int(rng.integers(low,high)); offsets[b,j]=shift
                rows.append(profile(i,np.roll(q,shift)))
            profiles[b]=np.mean(rows,axis=0)
        nulls[method]=profiles;shifts[method]=offsets
        center=profiles.mean(axis=0); excess=observed-center
        maxima=(profiles-center).max(axis=1)
        diagnostics[method]={
            'p_global':float((1+np.sum(maxima>=excess.max()))/(permutations+1)),
            'max_lag':int(lags[np.argmax(excess)]),
            'max_excess_bits':float(excess.max()),
            'null_max_95_bits':float(np.quantile(maxima,.95)),
            'pointwise_p':{str(k):float((1+np.sum(profiles[:,ix]-center[ix]>=excess[ix]))/(permutations+1)) for ix,k in enumerate(lags) if abs(k)==8},
            'null_mean_mi_bits':center.tolist(),
            'observed_excess_bits':excess.tolist(),
        }
    # Descriptive time variation in each channel; not a formal stationarity test.
    stats=[]
    for w,(i,q) in zip(selected,streams):
        stats.append({'window_index':int(w),'i_mean':float(i.mean()),'q_mean':float(q.mean()),
                      'i_std':float(i.std()),'q_std':float(q.std()),
                      'mi_lag_minus8':float(lagged_mi(i,q,-8,levels)),
                      'mi_lag_plus8':float(lagged_mi(i,q,8,levels))})
    out_dir.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out_dir/'null_profiles.npz',lags=lags,observed_windows=observed_windows,
        wide_null_profiles=nulls['wide'],half_turn_null_profiles=nulls['half_turn'],
        wide_shifts=shifts['wide'],half_turn_shifts=shifts['half_turn'])
    report={'schema':'virgo-rng-null-audit-v118','source':str(file),'source_bytes':size,
            'parameters':{'rate':rate,'window_seconds':window_seconds,'sample_pairs':sample_pairs,'windows':len(selected),
                          'max_lag':max_lag,'bits':bits,'permutations':permutations,'seed':seed},
            'lags':lags.tolist(),'observed_mi_bits':observed.tolist(),'methods':diagnostics,
            'per_window_diagnostics':stats,
            'limitations':['Both controls are circular shifts, not independent null families.',
                           'Comparing two shift ranges is a sensitivity check, not a proof of exchangeability.',
                           'Shared drift, spectral lines and periodic interference can invalidate both controls.',
                           'Per-window moments are descriptive, not a formal stationarity test.',
                           'The first capture is exploratory; confirmatory claims require a predeclared analysis.',
                           'No physical-coupling or cryptographic entropy conclusion follows.']}
    (out_dir/'null_audit_report.json').write_text(json.dumps(report,indent=2)+'\n')
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(11,5))
        for name in ('wide','half_turn'):
            ax.plot(lags,diagnostics[name]['observed_excess_bits'],label=f'{name}: p={diagnostics[name]["p_global"]:.3g}')
        ax.axhline(0,color='gray',lw=1);ax.set(xlabel='Lag k',ylabel='MI excess (bits)',title='Circular-shift null sensitivity audit')
        ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out_dir/'null_audit_plot.png',dpi=150);plt.close(fig)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file');p.add_argument('--out-dir',required=True)
    p.add_argument('--permutations',type=int,default=199)
    p.add_argument('--sample-pairs',type=int,default=30000)
    p.add_argument('--windows',type=int,default=12)
    p.add_argument('--rate',type=int,default=2400000)
    p.add_argument('--max-lag',type=int,default=32)
    p.add_argument('--seed',type=int,default=118)
    a=p.parse_args()
    result=run(a.file,a.out_dir,permutations=a.permutations,sample_pairs=a.sample_pairs,
               windows=a.windows,rate=a.rate,max_lag=a.max_lag,seed=a.seed)
    print(json.dumps({m:result['methods'][m]['p_global'] for m in result['methods']},indent=2))
if __name__=='__main__':main()
