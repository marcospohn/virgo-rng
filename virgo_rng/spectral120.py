"""Offline descriptive I/Q time/frequency analysis. Not an independence or entropy test."""
import argparse
import json
from pathlib import Path
import numpy as np


def analyze(path, out_dir, rate=2400000, windows=12, pairs=262144, max_lag=64, fft_size=4096):
    path=Path(path); out_dir=Path(out_dir)
    if rate<=0 or windows<1 or pairs<fft_size or fft_size<32 or max_lag<1 or max_lag>=pairs:
        raise ValueError('Invalid rate/windows/pairs/fft_size/max_lag')
    if fft_size & (fft_size-1): raise ValueError('fft_size must be a power of two')
    total=path.stat().st_size//2
    if total<pairs: raise ValueError('File too short for one window')
    starts=np.linspace(0,total-pairs,min(windows,(total-pairs)//pairs+1),dtype=np.int64)
    starts=np.unique(starts)
    lags=np.arange(-max_lag,max_lag+1)
    autoc_i=[]; autoc_q=[]; cross=[]; psdi=[]; psdq=[]; coherence=[]; phase=[]; diagnostics=[]
    taper=np.hanning(fft_size); norm=(taper*taper).sum()
    for index,start in enumerate(starts):
        with path.open('rb') as f:
            f.seek(int(start)*2); raw=np.frombuffer(f.read(pairs*2),dtype=np.uint8)
        if len(raw)!=pairs*2: raise IOError('Incomplete window')
        i=raw[::2].astype(np.float64)-127.5; q=raw[1::2].astype(np.float64)-127.5
        i-=i.mean(); q-=q.mean()
        si=i.std(); sq=q.std()
        if si==0 or sq==0: raise ValueError('Constant channel: correlation undefined')
        # Lag convention: corr(I[t],Q[t-k]).
        def corr(x,y,k):
            if k>0: a,b=x[k:],y[:-k]
            elif k<0: a,b=x[:k],y[-k:]
            else: a,b=x,y
            return float(np.dot(a,b)/(len(a)*x.std()*y.std()))
        autoc_i.append([corr(i,i,int(k)) for k in lags]); autoc_q.append([corr(q,q,int(k)) for k in lags]); cross.append([corr(i,q,int(k)) for k in lags])
        # Welch spectra with nonoverlapping segments, normalized to compare windows.
        a=(i[:(pairs//fft_size)*fft_size].reshape(-1,fft_size)*taper)
        b=(q[:(pairs//fft_size)*fft_size].reshape(-1,fft_size)*taper)
        A=np.fft.rfft(a,axis=1); B=np.fft.rfft(b,axis=1)
        pxx=np.mean(abs(A)**2,axis=0)/norm; pyy=np.mean(abs(B)**2,axis=0)/norm
        pxy=np.mean(A*np.conj(B),axis=0)/norm
        coh=np.abs(pxy)**2/np.maximum(pxx*pyy,np.finfo(float).tiny)
        psdi.append(pxx); psdq.append(pyy); coherence.append(coh);phase.append(np.angle(pxy))
        diagnostics.append({'window':index,'start_pair':int(start),'start_seconds':float(start/rate),'std_i':float(si),'std_q':float(sq),'corr_iq_zero':corr(i,q,0)})
    ai=np.mean(autoc_i,axis=0); aq=np.mean(autoc_q,axis=0); cq=np.mean(cross,axis=0)
    px=np.mean(psdi,axis=0); py=np.mean(psdq,axis=0)
    # Pooled Welch cross spectrum, rather than averaging coherence coefficients.
    # Recompute pooled CSD to preserve complex phase across windows.
    cross_spectra=[]
    for start in starts:
        with path.open('rb') as f:
            f.seek(int(start)*2); raw=np.frombuffer(f.read(pairs*2),dtype=np.uint8)
        i=raw[::2].astype(float);q=raw[1::2].astype(float);i-=i.mean();q-=q.mean()
        A=np.fft.rfft(i.reshape(-1,fft_size)*taper,axis=1)
        B=np.fft.rfft(q.reshape(-1,fft_size)*taper,axis=1)
        cross_spectra.append(np.mean(A*np.conj(B),axis=0)/norm)
    pxy=np.mean(cross_spectra,axis=0)
    coh=np.clip(np.abs(pxy)**2/np.maximum(px*py,np.finfo(float).tiny),0,1)
    freq=np.fft.rfftfreq(fft_size,d=1/rate)
    peak_indices=np.argsort(np.abs(cq))[-10:][::-1]
    report={'schema':'virgo-rng-spectral-v120','source':str(path),'source_bytes':path.stat().st_size,
        'parameters':{'rate':rate,'windows_requested':windows,'windows_used':len(starts),'pairs_per_window':pairs,'max_lag':max_lag,'fft_size':fft_size},
        'coverage':{'analyzed_pairs':int(len(starts)*pairs),'fraction_of_file':float(len(starts)*pairs/total),'window_starts_seconds':[float(s/rate) for s in starts]},
        'lags':lags.tolist(),'autocorrelation_i':ai.tolist(),'autocorrelation_q':aq.tolist(),'cross_correlation_iq':cq.tolist(),
        'cross_correlation_peak_lags':[{'lag':int(lags[j]),'coefficient':float(cq[j])} for j in peak_indices],
        'cross_correlation_at_minus8':float(cq[max_lag-8]) if max_lag>=8 else None,
        'cross_correlation_at_plus8':float(cq[max_lag+8]) if max_lag>=8 else None,
        'frequency_hz':freq.tolist(),'psd_i_db':(10*np.log10(np.maximum(px,1e-30))).tolist(),
        'psd_q_db':(10*np.log10(np.maximum(py,1e-30))).tolist(),
        'magnitude_squared_coherence':coh.tolist(),'cross_spectral_phase_radians':np.angle(pxy).tolist(),
        'window_diagnostics':diagnostics,
        'limitations':['Descriptive linear correlation and spectral coherence only; nonlinear dependence can be missed.',
          'Welch coherence has finite-sample positive bias and no significance threshold here.',
          'Sparse windows do not cover the full file; no stationarity proof.',
          'No physical source attribution, independence certification or cryptographic entropy estimate.']}
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/'spectral_report.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(3,1,figsize=(12,12),constrained_layout=True)
        ax[0].plot(lags,ai,label='I autocorrelation');ax[0].plot(lags,aq,label='Q autocorrelation');ax[0].plot(lags,cq,label='I/Q cross correlation');ax[0].legend();ax[0].set(xlabel='Lag (I/Q pairs)',ylabel='Pearson correlation',title='Time-domain correlation (window average)');ax[0].grid(alpha=.25)
        ax[1].plot(freq/1e3,report['psd_i_db'],label='I PSD');ax[1].plot(freq/1e3,report['psd_q_db'],label='Q PSD');ax[1].legend();ax[1].set(xlabel='Baseband frequency (kHz)',ylabel='Relative power (dB)',title='Welch spectra');ax[1].grid(alpha=.25)
        ax[2].plot(freq/1e3,coh);ax[2].set(xlabel='Baseband frequency (kHz)',ylabel='Magnitude-squared coherence',ylim=(0,1),title='Cross-channel spectral coherence (descriptive)');ax[2].grid(alpha=.25)
        fig.savefig(out_dir/'spectral_plot.png',dpi=150);plt.close(fig)
    except ImportError: pass
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file',type=Path);p.add_argument('--out-dir',type=Path,required=True)
    p.add_argument('--rate',type=int,default=2400000);p.add_argument('--windows',type=int,default=12)
    p.add_argument('--pairs',type=int,default=262144);p.add_argument('--max-lag',type=int,default=64)
    p.add_argument('--fft-size',type=int,default=4096)
    args=p.parse_args(); r=analyze(args.file,args.out_dir,args.rate,args.windows,args.pairs,args.max_lag,args.fft_size)
    print(json.dumps({'report':str(args.out_dir/'spectral_report.json'),'coverage':r['coverage'],'peaks':r['cross_correlation_peak_lags'][:3]},indent=2))
if __name__=='__main__': main()
