"""Offline empirical I/Q dependence diagnostics; not a cryptographic entropy estimate."""
from pathlib import Path
import hashlib, json, math
import numpy as np

def _entropy(counts):
    c=np.asarray(counts,dtype=np.float64).ravel()
    p=c[c>0]/c.sum()
    return float(-np.sum(p*np.log2(p)))

def _corr(a,b):
    x=a.astype(np.float64);y=b.astype(np.float64)
    x-=x.mean();y-=y.mean()
    den=np.sqrt(np.dot(x,x)*np.dot(y,y))
    return float(np.dot(x,y)/den) if den else None

def analyze_file(file, *, out_dir, chunk_pairs=1000000, max_lag=32, lag_pairs=200000, plot=True):
    file=Path(file);out_dir=Path(out_dir)
    if chunk_pairs<2 or lag_pairs<max_lag+2 or max_lag<0:raise ValueError('Invalid analysis parameters')
    size=file.stat().st_size
    if size%2 or size<4:raise ValueError('CU8 file must contain complete I/Q pairs')
    out_dir.mkdir(parents=True,exist_ok=True)
    joint=np.zeros(65536,dtype=np.int64);sha=hashlib.sha256();total=0
    # Streaming histogram: every sample pair contributes, memory stays bounded.
    with file.open('rb') as f:
        while raw:=f.read(chunk_pairs*2):
            if len(raw)%2:raise ValueError('Incomplete pair')
            sha.update(raw)
            iq=np.frombuffer(raw,dtype=np.uint8).reshape(-1,2)
            idx=iq[:,0].astype(np.uint16)*256+iq[:,1].astype(np.uint16)
            joint+=np.bincount(idx,minlength=65536)
            total+=len(iq)
    joint=joint.reshape(256,256)
    hi=_entropy(joint.sum(axis=1));hq=_entropy(joint.sum(axis=0));hjoint=_entropy(joint)
    n=min(lag_pairs,total)
    with file.open('rb') as f:raw=f.read(n*2)
    a=np.frombuffer(raw,dtype=np.uint8).reshape(-1,2)
    i=a[:,0];q=a[:,1]
    lags=[]
    for lag in range(max_lag+1):
        if lag==0:
            lags.append({'lag':0,'i_i':1.0,'q_q':1.0,'i_q':_corr(i,q),'q_i':_corr(q,i)})
        else:
            lags.append({'lag':lag,'i_i':_corr(i[:-lag],i[lag:]),'q_q':_corr(q[:-lag],q[lag:]),'i_q':_corr(i[:-lag],q[lag:]),'q_i':_corr(q[:-lag],i[lag:])})
    result={'schema':'virgo-rng-dependence-v1','source':str(file),'sha256':sha.hexdigest(),'total_pairs':total,
      'histogram_scope':'all pairs','lag_scope':'first contiguous pairs only','lag_pairs_analyzed':n,
      'shannon_bits':{'i':hi,'q':hq,'joint_iq':hjoint,'q_given_i':hjoint-hi,'i_given_q':hjoint-hq,'mutual_information':hi+hq-hjoint},
      'cross_correlation_lag0':lags[0]['i_q'],'lag_correlations':lags,
      'limitations':['Shannon entropies are empirical marginal/joint estimates, NOT cryptographic min-entropy or extractable random bits.',
       'Lag correlations use only the first contiguous segment, not the full recording.',
       'Zero Pearson correlation does not establish statistical independence.',
       'I/Q channels and successive samples may share hidden dependencies; no entropy certification.']}
    (out_dir/'dependence_report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(2,1,figsize=(10,8))
        axes[0].imshow(np.log1p(joint),origin='lower',aspect='auto',cmap='viridis')
        axes[0].set(xlabel='Q byte value',ylabel='I byte value',title='Log(1 + count) joint histogram')
        for key in ('i_i','q_q','i_q','q_i'):
            axes[1].plot([d['lag'] for d in lags],[d[key] for d in lags],label=key)
        axes[1].set(xlabel='Lag (I/Q pairs)',ylabel='Pearson correlation',title='First contiguous segment')
        axes[1].legend();fig.tight_layout();fig.savefig(out_dir/'dependence_plot.png',dpi=150);plt.close(fig)
    return result
