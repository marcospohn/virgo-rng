"""Exploratory temporal conditional Shannon entropy, never min-entropy."""
from pathlib import Path
import json, math
import numpy as np

def entropy(c):
    c=np.asarray(c,dtype=np.float64).ravel(); c=c[c>0]
    if not len(c): return None
    p=c/c.sum()
    return float(-(p*np.log2(p)).sum())

def conditional(a,b,alphabet=256):
    # H(a|b) with current symbol a and predecessor b.
    h=np.bincount(b.astype(np.int32)*alphabet+a.astype(np.int32),minlength=alphabet**2).reshape(alphabet,alphabet)
    return entropy(h)-entropy(h.sum(axis=1))

def analyze_file(file, *, out_dir, rate=2400000, window_seconds=1.0, sample_pairs=200000, plot=True):
    file=Path(file); out_dir=Path(out_dir)
    if rate<=0 or window_seconds<=0 or sample_pairs<1000: raise ValueError('Invalid parameters')
    wp=round(rate*window_seconds)
    if wp<sample_pairs: raise ValueError('Window smaller than sample_pairs')
    if file.stat().st_size%2: raise ValueError('Incomplete I/Q pair')
    count=file.stat().st_size//2
    nw=count//wp
    if not nw: raise ValueError('No complete window')
    out_dir.mkdir(parents=True,exist_ok=True)
    windows=[]
    with file.open('rb') as f:
        for w in range(nw):
            f.seek(w*wp*2)
            raw=f.read(sample_pairs*2)
            if len(raw)!=sample_pairs*2: raise IOError('Short read')
            iq=np.frombuffer(raw,dtype=np.uint8).reshape(-1,2)
            i=iq[:,0];q=iq[:,1]
            # Full 8-bit one-step conditional entropies per channel.
            hi=entropy(np.bincount(i,minlength=256));hq=entropy(np.bincount(q,minlength=256))
            ci=conditional(i[1:],i[:-1]);cq=conditional(q[1:],q[:-1])
            # Coarse 4-bit per component joint-pair transition, 256x256 bins.
            # Quantization and finite sample bias make this exploratory only.
            state=(i.astype(np.uint16)//16)*16+(q.astype(np.uint16)//16)
            hstate=entropy(np.bincount(state,minlength=256))
            cstate=conditional(state[1:],state[:-1])
            windows.append({'index':w,'start_seconds':w*wp/rate,'pairs_analyzed':sample_pairs,
                'i_shannon_bits':hi,'q_shannon_bits':hq,
                'i_given_previous_i_bits':ci,'q_given_previous_q_bits':cq,
                'i_temporal_mutual_information_bits':hi-ci,
                'q_temporal_mutual_information_bits':hq-cq,
                'coarse_joint_iq_shannon_bits':hstate,
                'coarse_joint_iq_given_previous_joint_bits':cstate,
                'coarse_joint_temporal_mutual_information_bits':hstate-cstate})
    keys=[k for k in windows[0] if k.endswith('bits')]
    summary={k:{'mean':float(np.mean([v[k] for v in windows])), 'min':float(np.min([v[k] for v in windows])), 'max':float(np.max([v[k] for v in windows]))} for k in keys}
    result={'schema':'virgo-rng-temporal-dependence-v1','source':str(file),'file_bytes':file.stat().st_size,
      'total_pairs':count,'window_pairs':wp,'window_seconds':wp/rate,'sample_pairs_per_window':sample_pairs,
      'windows_analyzed':nw,'trailing_pairs_not_analyzed':count-nw*wp,'summary':summary,'windows':windows,
      'limitations':['All entropy values are empirical Shannon estimates, not cryptographic min-entropy.',
      'One-step conditional entropies do not capture dependencies on longer histories.',
      'Only the first sample_pairs contiguous pairs of each window are analyzed; results may be biased by selection.',
      'Coarse joint transition analysis quantizes each 8-bit component to 4 bits; results are not comparable to full-resolution joint entropy.',
      'Plug-in conditional entropy estimates can be biased with finite samples, particularly for the 256-state transition table.',
      'Window-to-window nonstationarity and receiver/PLL issues are not resolved by these measurements.']}
    (out_dir/'temporal_dependence_report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        x=[v['start_seconds'] for v in windows]
        fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True)
        for k in ('i_shannon_bits','i_given_previous_i_bits','q_given_previous_q_bits'):
            axes[0].plot(x,[v[k] for v in windows],label=k)
        for k in ('coarse_joint_iq_shannon_bits','coarse_joint_iq_given_previous_joint_bits'):
            axes[1].plot(x,[v[k] for v in windows],label=k)
        axes[0].set(ylabel='Bits / 8-bit sample',title='One-step conditional Shannon entropy')
        axes[1].set(xlabel='Seconds',ylabel='Bits / quantized I/Q pair',title='Exploratory 4-bit/component joint transitions')
        for ax in axes: ax.legend(fontsize=8);ax.grid(alpha=.2)
        fig.tight_layout();fig.savefig(out_dir/'temporal_dependence_plot.png',dpi=150);plt.close(fig)
    return result
