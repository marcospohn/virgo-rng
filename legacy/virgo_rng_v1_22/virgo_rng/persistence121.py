"""Window-by-window I/Q correlation persistence, descriptive only."""
import argparse
import json
from pathlib import Path
import numpy as np


def analyze(path, out_dir, rate=2400000, windows=120, pairs=65536, lags=(8,41)):
    path=Path(path); out_dir=Path(out_dir)
    if rate<=0 or windows<2 or pairs<128 or any(k<1 or k>=pairs for k in lags):
        raise ValueError("Invalid rate, windows, pairs or lags")
    total=path.stat().st_size//2
    if total<2*pairs: raise ValueError("At least two windows required")
    starts=np.unique(np.linspace(0,total-pairs,min(windows,total//pairs),dtype=np.int64))
    records=[]
    for n,start in enumerate(starts):
        with path.open('rb') as f:
            f.seek(int(start)*2)
            raw=np.frombuffer(f.read(pairs*2),dtype=np.uint8)
        if raw.size!=pairs*2: raise IOError("Incomplete window")
        i=raw[::2].astype(np.float64); q=raw[1::2].astype(np.float64)
        i-=i.mean(); q-=q.mean()
        si=np.sqrt(np.mean(i*i)); sq=np.sqrt(np.mean(q*q))
        if si==0 or sq==0: raise ValueError("Constant channel")
        def corr(x,y,k,sx,sy):
            if k>0: a,b=x[k:],y[:-k]
            elif k<0: a,b=x[:k],y[-k:]
            else: a,b=x,y
            return float(np.mean(a*b)/(sx*sy))
        r={'window':n,'start_seconds':float(start/rate),
           'auto_i_lag1':corr(i,i,1,si,si),'auto_q_lag1':corr(q,q,1,sq,sq),
           'cross_zero':corr(i,q,0,si,sq)}
        for k in lags:
            r[f'cross_minus{k}']=corr(i,q,-k,si,sq)
            r[f'cross_plus{k}']=corr(i,q,k,si,sq)
            r[f'antisymmetry_{k}']=0.5*(r[f'cross_plus{k}']-r[f'cross_minus{k}'])
        records.append(r)
    keys=[k for k in records[0] if k not in ('window','start_seconds')]
    summary={}
    for key in keys:
        values=np.array([r[key] for r in records]); positive=int(np.sum(values>0)); negative=int(np.sum(values<0))
        summary[key]={'mean':float(values.mean()),'std_across_windows':float(values.std(ddof=1)),
                      'min':float(values.min()),'max':float(values.max()),
                      'positive_windows':positive,'negative_windows':negative,
                      'same_sign_as_mean_fraction':float(max(positive,negative)/len(values))}
    report={'schema':'virgo-rng-persistence-v121','source':str(path),
            'parameters':{'rate':rate,'windows_requested':windows,'windows_used':len(records),
                          'pairs_per_window':pairs,'lags':list(lags)},
            'coverage':{'fraction_of_file':float(len(records)*pairs/total),
                        'analyzed_pairs':int(len(records)*pairs)},
            'summary':summary,'windows':records,
            'limitations':['Descriptive persistence only; no calibrated hypothesis test.',
                           'Window statistics may be dependent; no independence assumption or confidence interval.',
                           'Sparse windows do not cover the full recording.',
                           'No entropy estimate or physical source attribution.']}
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/'persistence_report.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        t=[r['start_seconds'] for r in records]
        fig,axes=plt.subplots(3,1,figsize=(12,10),constrained_layout=True)
        axes[0].plot(t,[r['auto_i_lag1'] for r in records],label='I lag 1')
        axes[0].plot(t,[r['auto_q_lag1'] for r in records],label='Q lag 1')
        axes[0].set_title('Lag-1 temporal autocorrelation')
        for k in lags:
            axes[1].plot(t,[r[f'cross_plus{k}'] for r in records],label=f'I/Q +{k}')
            axes[1].plot(t,[r[f'cross_minus{k}'] for r in records],label=f'I/Q -{k}')
            axes[2].plot(t,[r[f'antisymmetry_{k}'] for r in records],label=f'Antisymmetric component ±{k}')
        axes[1].set_title('Cross-channel correlation by window')
        axes[2].set_title('Antisymmetric I/Q component')
        for ax in axes:
            ax.axhline(0,color='gray',linewidth=.8)
            ax.set(xlabel='Time in recording (s)',ylabel='Pearson correlation')
            ax.legend();ax.grid(alpha=.2)
        fig.savefig(out_dir/'persistence_plot.png',dpi=150);plt.close(fig)
    except ImportError: pass
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file',type=Path);p.add_argument('--out-dir',type=Path,required=True)
    p.add_argument('--rate',type=int,default=2400000)
    p.add_argument('--windows',type=int,default=120)
    p.add_argument('--pairs',type=int,default=65536)
    args=p.parse_args()
    analyze(args.file,args.out_dir,args.rate,args.windows,args.pairs)


if __name__=='__main__': main()
