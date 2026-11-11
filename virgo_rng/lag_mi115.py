"""Exploratory lagged mutual information between quantized I and Q."""
import json
from pathlib import Path
import numpy as np


def mutual_information(a,b,levels):
    """Plugin estimate, bits; positively biased at finite sample size."""
    if len(a)!=len(b) or len(a)==0: raise ValueError('Nonempty equal-length arrays required')
    counts=np.bincount(a.astype(np.int64)*levels+b.astype(np.int64),minlength=levels*levels).reshape(levels,levels).astype(float)
    p=counts/counts.sum(); pa=p.sum(axis=1); pb=p.sum(axis=0)
    expected=pa[:,None]*pb[None,:]
    mask=p>0
    return float(np.sum(p[mask]*np.log2(p[mask]/expected[mask])))


def lagged_mi(i,q,lag,levels):
    """MI(I[t], Q[t-lag]); positive lag means Q precedes I."""
    if abs(lag)>=len(i):raise ValueError('Lag too large')
    if lag>0:return mutual_information(i[lag:],q[:-lag],levels)
    if lag<0:return mutual_information(i[:lag],q[-lag:],levels)
    return mutual_information(i,q,levels)


def analyze_file(file,*,out_dir,rate=2400000,window_seconds=1.,sample_pairs=120000,
                 windows=12,max_lag=32,quantization_bits=4,control_repeats=10,seed=115,plot=True):
    file=Path(file);out_dir=Path(out_dir)
    if rate<=0 or window_seconds<=0 or sample_pairs<1000 or windows<2 or max_lag<1 or max_lag>=sample_pairs//4 or quantization_bits not in (2,3,4,5,6,7,8) or control_repeats<1:
        raise ValueError('Invalid parameters')
    wp=round(rate*window_seconds)
    if sample_pairs>wp:raise ValueError('sample_pairs exceeds window')
    size=file.stat().st_size
    if size%2:raise ValueError('Incomplete I/Q pair')
    total=size//2; nw=total//wp
    if nw<2:raise ValueError('Need at least two complete windows')
    selected=np.unique(np.linspace(0,nw-1,min(windows,nw),dtype=int))
    lags=list(range(-max_lag,max_lag+1));levels=1<<quantization_bits
    observed=[];controls=[];window_rows=[]
    with file.open('rb') as f:
        for w in selected:
            f.seek(int(w)*wp*2);raw=f.read(sample_pairs*2)
            if len(raw)!=sample_pairs*2:raise IOError('Short read')
            iq=np.frombuffer(raw,dtype=np.uint8).reshape(-1,2)
            i=iq[:,0]>>(8-quantization_bits);q=iq[:,1]>>(8-quantization_bits)
            obs=np.array([lagged_mi(i,q,k,levels) for k in lags])
            rng=np.random.default_rng(seed+int(w)*7919)
            ctr=[]
            # Random circular shifts preserve within-channel order and histogram;
            # offsets exclude the evaluated lag neighborhood.
            low=max(2*max_lag+1,len(i)//10)
            high=len(i)-low
            if high<=low:raise ValueError('Insufficient samples for separated shift controls')
            for _ in range(control_repeats):
                shifted=np.roll(q,int(rng.integers(low,high)))
                ctr.append([lagged_mi(i,shifted,k,levels) for k in lags])
            ctr=np.array(ctr)
            observed.append(obs);controls.append(ctr)
            window_rows.append({'window_index':int(w),'start_seconds':float(w*window_seconds),
                'observed_mi_bits':obs.tolist(),'shifted_control_mean_mi_bits':ctr.mean(axis=0).tolist()})
    obs=np.stack(observed);ctrl=np.stack(controls)
    # Paired window differences mitigate the positive finite-sample plug-in bias.
    diff=obs-ctrl.mean(axis=1)
    n=len(selected);se=diff.std(axis=0,ddof=1)/np.sqrt(n)
    mean=diff.mean(axis=0)
    # Descriptive normal-approximation intervals; windows may not be independent.
    result={'schema':'virgo-rng-lag-mi-v1','source':str(file),'source_bytes':size,'total_pairs':total,
        'window_indices':selected.tolist(),'sample_pairs_per_window':sample_pairs,
        'quantization_bits_per_component':quantization_bits,'max_lag':max_lag,
        'control_repeats_per_window':control_repeats,'seed':seed,
        'lag_definition':'MI(I[t]; Q[t-k]); k>0 means Q precedes I',
        'lags':lags,'summary':{'observed_mi_mean_bits':obs.mean(axis=0).tolist(),
          'shifted_control_mean_bits':ctrl.mean(axis=(0,1)).tolist(),
          'excess_over_control_mean_bits':mean.tolist(),
          'excess_approx_95ci_low_bits':(mean-1.96*se).tolist(),
          'excess_approx_95ci_high_bits':(mean+1.96*se).tolist(),
          'excess_window_standard_error_bits':se.tolist(),
          'max_excess_lag':lags[int(np.argmax(mean))],
          'max_excess_bits':float(mean.max())},'windows':window_rows,
        'limitations':['Plug-in MI has positive finite-sample bias; use shifted controls for comparison.',
          'Pointwise normal intervals are descriptive, not multiple-comparison-adjusted.',
          'Window estimates may be dependent; 12 windows are not 12 independent acquisitions.',
          'Circular shifts can retain shared drift or periodicity.',
          'Quantization can conceal dependencies in discarded bits.',
          'Positive MI does not establish causal coupling, cryptographic predictability or min-entropy.']}
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/'lag_mi_report.json').write_text(json.dumps(result,indent=2)+'\n')
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
        axes[0].plot(lags,obs.mean(axis=0),label='Observed MI')
        axes[0].plot(lags,ctrl.mean(axis=(0,1)),label='Shifted-channel control')
        axes[0].set_ylabel('MI (bits)');axes[0].legend();axes[0].grid(alpha=.2)
        axes[1].plot(lags,mean,label='Excess MI over control')
        axes[1].fill_between(lags,mean-1.96*se,mean+1.96*se,alpha=.2,label='Approx. pointwise 95% interval')
        axes[1].axhline(0,color='gray',lw=1)
        axes[1].set_xlabel('Lag k: MI(I[t]; Q[t-k])');axes[1].set_ylabel('Excess MI (bits)')
        axes[1].legend();axes[1].grid(alpha=.2)
        fig.tight_layout();fig.savefig(out_dir/'lag_mi_plot.png',dpi=160);plt.close(fig)
    return result
