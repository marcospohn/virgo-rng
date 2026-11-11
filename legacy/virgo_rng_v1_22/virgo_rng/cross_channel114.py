"""Held-out incremental cross-channel prediction; exploratory, not min-entropy."""
import json
from pathlib import Path
import numpy as np

ORDERS=(1,2,4)

def _contexts(own, other, k, both):
    n=len(own)
    codes=np.zeros(n-k,dtype=np.int64)
    for j in range(k):
        codes=codes*4+own[j:n-k+j].astype(np.int64)
        if both:
            codes=codes*4+other[j:n-k+j].astype(np.int64)
    return codes

def _probabilities(target, own, other, k, train_end, test_start, both, alpha=30.0, fallback=None):
    n=len(target)
    ctx_train=_contexts(own[:train_end],other[:train_end],k,both)
    y_train=target[k:train_end].astype(np.int64)
    ctx_test=_contexts(own,other,k,both)[test_start-k:n-k]
    y_test=target[test_start:].astype(np.int64)
    base=4
    keys=ctx_train*base+y_train
    unique, counts=np.unique(keys,return_counts=True)
    ctx_unique, starts=np.unique(unique//base,return_index=True)
    totals=np.add.reduceat(counts,starts).astype(float)
    loc=np.searchsorted(ctx_unique,ctx_test)
    valid=loc<len(ctx_unique)
    found=np.zeros(len(loc),dtype=bool)
    found[valid]=ctx_unique[loc[valid]]==ctx_test[valid]
    denominators=np.zeros(len(loc),dtype=float)
    denominators[found]=totals[loc[found]]
    qkeys=ctx_test*base+y_test
    idx=np.searchsorted(unique,qkeys)
    hit=np.zeros(len(idx),dtype=float)
    ok=idx<len(unique)
    ok[ok]=unique[idx[ok]]==qkeys[ok]
    hit[ok]=counts[idx[ok]]
    if fallback is None:
        freq=np.bincount(target[:train_end],minlength=4).astype(float)
        fallback=(freq[y_test]+0.5)/(freq.sum()+2.0)
    probs=(hit+alpha*fallback)/(denominators+alpha)
    return probs,float(np.mean(~found))

def evaluate(i,q,*,alpha=30.0,train_fraction=0.7):
    i=np.asarray(i,dtype=np.uint8);q=np.asarray(q,dtype=np.uint8)
    if len(i)!=len(q) or len(i)<100 or i.max()>3 or q.max()>3:raise ValueError('Expected equal 2-bit channels')
    split=int(len(i)*train_fraction);test_start=split+max(ORDERS)
    if test_start>=len(i):raise ValueError('Insufficient test samples')
    out={}
    for name,target,other in [('i',i,q),('q',q,i)]:
        vals=[]
        for k in ORDERS:
            own,unseen_own=_probabilities(target,target,other,k,split,test_start,False,alpha)
            combined,unseen_both=_probabilities(target,target,other,k,split,test_start,True,alpha,fallback=own)
            l_own=float(np.mean(-np.log2(own)));l_both=float(np.mean(-np.log2(combined)))
            vals.append({'history':k,'own_only_logloss_bits':l_own,'own_and_other_logloss_bits':l_both,
                         'incremental_other_channel_gain_bits':l_own-l_both,
                         'unseen_own_fraction':unseen_own,'unseen_combined_fraction':unseen_both})
        out[name]=vals
    return out

def analyze_file(file,*,out_dir,rate=2400000,window_seconds=1.,sample_pairs=120000,windows=12,
                 shuffle_repeats=3,alpha=30.,plot=True):
    file=Path(file);out_dir=Path(out_dir)
    if rate<=0 or window_seconds<=0 or sample_pairs<1000 or windows<1 or shuffle_repeats<1 or alpha<=0:raise ValueError('Invalid parameters')
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
            f.seek(int(w)*wp*2);raw=f.read(sample_pairs*2)
            if len(raw)!=sample_pairs*2:raise IOError('Short read')
            iq=np.frombuffer(raw,dtype=np.uint8).reshape(-1,2)
            i=(iq[:,0]>>6).copy();q=(iq[:,1]>>6).copy()
            obs=evaluate(i,q,alpha=alpha)
            controls=[]
            for r in range(shuffle_repeats):
                rng=np.random.default_rng(114000+int(w)*97+r)
                # Independent random circular shifts of the other channel preserve its own temporal structure,
                # but destroy alignment with target. Use offsets far from 0 and dataset edges.
                offset=int(rng.integers(max(10,len(i)//10),max(11,len(i)*9//10)))
                qs=np.roll(q,offset)
                controls.append(evaluate(i,qs,alpha=alpha))
            for channel in ('i','q'):
                for j,k in enumerate(ORDERS):
                    vals=np.array([c[channel][j]['incremental_other_channel_gain_bits'] for c in controls])
                    obs[channel][j]['shifted_control_mean_gain_bits']=float(vals.mean())
                    obs[channel][j]['shifted_control_std_gain_bits']=float(vals.std(ddof=1)) if len(vals)>1 else None
                    obs[channel][j]['excess_over_shifted_mean_bits']=float(obs[channel][j]['incremental_other_channel_gain_bits']-vals.mean())
            rows.append({'window_index':int(w),'start_seconds':float(w*wp/rate),'metrics':obs})
    summary={channel:{str(k):{field:float(np.mean([row['metrics'][channel][j][field] for row in rows]))
                    for field in ('own_only_logloss_bits','own_and_other_logloss_bits','incremental_other_channel_gain_bits',
                                  'unseen_combined_fraction','shifted_control_mean_gain_bits','excess_over_shifted_mean_bits')}
                    for j,k in enumerate(ORDERS)} for channel in ('i','q')}
    report={'schema':'virgo-rng-cross-channel-v1','source':str(file),'source_bytes':size,'total_pairs':total,
            'windows_selected':selected.tolist(),'sample_pairs_per_window':sample_pairs,
            'quantization_bits_per_component':2,'train_fraction':0.7,'context_orders':list(ORDERS),
            'shift_control_repeats':shuffle_repeats,'smoothing_alpha':alpha,'summary':summary,'windows':rows,
            'limitations':['Conditional held-out log loss is not min-entropy or cryptographic certification.',
             'The comparison is model-specific; small gain does not prove conditional independence.',
             '2-bit quantization discards 6 bits per original component.',
             'Circular shifts preserve temporal ordering of each channel but can retain long-timescale common drift.',
             'Results average selected windows and do not constitute a confidence bound.']}
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/'cross_channel_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axs=plt.subplots(2,1,figsize=(9,7),sharex=True)
        for ax,channel in zip(axs,('i','q')):
            ax.plot(ORDERS,[summary[channel][str(k)]['incremental_other_channel_gain_bits'] for k in ORDERS],marker='o',label='Observed extra-channel gain')
            ax.plot(ORDERS,[summary[channel][str(k)]['shifted_control_mean_gain_bits'] for k in ORDERS],marker='o',label='Shifted-channel control')
            ax.axhline(0,color='gray',lw=.8);ax.set(ylabel='Gain (bits / 2-bit symbol)',title=f'Target {channel.upper()}');ax.legend();ax.grid(alpha=.2)
        axs[-1].set(xlabel='Previous samples per channel',xticks=ORDERS)
        fig.suptitle('Incremental prediction from the other I/Q channel')
        fig.tight_layout();fig.savefig(out_dir/'cross_channel_plot.png',dpi=150);plt.close(fig)
    return report
