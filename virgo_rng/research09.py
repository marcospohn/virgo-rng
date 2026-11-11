"""Exploratory multi-history prediction, change points, and campaign summaries."""
import json
from pathlib import Path
import numpy as np
from .validation import _read_channel, window_diagnostics, save_report


def predictor_histories(a, histories=(0, 1, 2), train_fraction=0.5):
    """Chronological held-out empirical n-gram predictors; never an entropy bound."""
    a=np.asarray(a,dtype=np.uint8)
    if len(a)<1000: raise ValueError('Need at least 1000 observations')
    split=int(len(a)*train_fraction)
    if split<100 or split>=len(a)-100: raise ValueError('Invalid split')
    mode=int(np.bincount(a[:split],minlength=256).argmax())
    out=[]
    for h in histories:
        if h<0 or h>3: raise ValueError('History must be 0..3')
        counts={}
        if h:
            for i in range(h,split):
                key=bytes(a[i-h:i]); target=int(a[i]); row=counts.get(key)
                if row is None: row=np.zeros(256,dtype=np.int32); counts[key]=row
                row[target]+=1
            guesses={k:int(v.argmax()) for k,v in counts.items()}
        else: guesses={}
        hits=0; unseen=0
        for i in range(split,len(a)):
            key=bytes(a[i-h:i]) if h else b''
            if h and key not in guesses: unseen+=1
            guess=guesses.get(key,mode)
            hits+=guess==int(a[i])
        baseline=int(np.count_nonzero(a[split:]==mode))
        out.append({'history_length':h,'training_samples':split,'test_samples':len(a)-split,
                    'accuracy':hits/(len(a)-split),'baseline_accuracy':baseline/(len(a)-split),
                    'unseen_context_fraction':unseen/(len(a)-split),
                    'contexts_trained':len(guesses)})
    return out


def change_diagnostics(windows, threshold=4.0):
    """Robust median/MAD deviation flags, descriptive only, not a calibrated detector."""
    if threshold<=0: raise ValueError('threshold must be positive')
    keys=('std','max_symbol_fraction','acf1')
    summary={}; flagged=set()
    for key in keys:
        x=np.asarray([w[key] for w in windows],dtype=float)
        center=float(np.median(x)); mad=float(np.median(np.abs(x-center)))
        scale=max(1.4826*mad,1e-9)
        flags=np.flatnonzero(np.abs(x-center)>threshold*scale).tolist()
        summary[key]={'median':center,'scaled_mad':scale,'flagged_window_indices':flags}
        flagged.update(flags)
    return {'threshold_robust_z':threshold,'metrics':summary,'flagged_windows':sorted(flagged),
            'warning':'Exploratory outlier flags; no significance or entropy certification'}


def research_report(path,channel='i',max_bytes=2_000_000,window_samples=16384,skip_bytes=0):
    report=window_diagnostics(path,channel=channel,max_bytes=max_bytes,
                              window_samples=window_samples,skip_bytes=skip_bytes)
    a=_read_channel(path,max_bytes,channel,skip_bytes)
    report['multi_history_prediction']=predictor_histories(a)
    report['change_diagnostics']=change_diagnostics(report['windows'])
    report['method']='Chronological holdout, n-gram majority prediction, robust window deviations'
    report['security_status']='UNVALIDATED_NOT_FOR_CRYPTOGRAPHY'
    return report


def campaign_summary(paths):
    entries=[]
    for p in paths:
        obj=json.loads(Path(p).read_text(encoding='utf-8'))
        if 'multi_history_prediction' not in obj or 'windows' not in obj:
            raise ValueError(f'Not a v0.9 research report: {p}')
        entries.append({'report':str(p),'channel':obj.get('channel'),
                        'source_bytes':obj.get('bytes_read'),
                        'window_count':len(obj['windows']),
                        'flagged_windows':len(obj['change_diagnostics']['flagged_windows']),
                        'prediction':obj['multi_history_prediction']})
    return {'security_status':'UNVALIDATED_NOT_FOR_CRYPTOGRAPHY','campaigns':entries,
            'warning':'Captures and windows may be dependent; this is not a pooled entropy estimate'}


def plot_dashboard(report,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    w=report['windows']; idx=np.arange(len(w))
    fig,axs=plt.subplots(2,2,figsize=(11,7))
    for ax,key,label in zip(axs.flat[:3],('std','max_symbol_fraction','acf1'),
                             ('Standard deviation','Max symbol fraction','Lag-1 autocorrelation')):
        ax.plot(idx,[r[key] for r in w],linewidth=1)
        flagged=report['change_diagnostics']['metrics'][key]['flagged_window_indices']
        if flagged: ax.scatter(flagged,[w[i][key] for i in flagged],marker='x')
        ax.set(xlabel='Window index',ylabel=label);ax.grid(alpha=.2)
    pred=report['multi_history_prediction']
    axs.flat[3].plot([p['history_length'] for p in pred],[p['accuracy'] for p in pred],marker='o',label='Predictor')
    axs.flat[3].plot([p['history_length'] for p in pred],[p['baseline_accuracy'] for p in pred],linestyle='--',label='Constant baseline')
    axs.flat[3].set(xlabel='History length',ylabel='Held-out accuracy');axs.flat[3].legend()
    fig.suptitle('Virgo-RNG v0.9 — EXPLORATORY, NOT CRYPTOGRAPHICALLY VALIDATED')
    fig.tight_layout();output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=130);plt.close(fig)
