"""Startup/transient diagnostics; descriptive statistics, not entropy certification."""
import math
from pathlib import Path
import numpy as np
from .validation import _read_channel


def transient_report(path, *, channel='i', max_bytes=4_000_000, window_samples=4096, skip_bytes=0):
    if window_samples < 256:
        raise ValueError('window_samples must be >= 256')
    a = _read_channel(path, max_bytes=max_bytes, channel=channel, skip_bytes=skip_bytes)
    n = len(a) // window_samples
    if n < 4:
        raise ValueError('Need at least four complete windows')
    windows = []
    for i in range(n):
        x = a[i*window_samples:(i+1)*window_samples]
        counts = np.bincount(x, minlength=256)
        top = float(counts.max()/len(x))
        y = x.astype(np.float64)
        y -= y.mean()
        den = float(np.dot(y,y))
        windows.append({'index':i,'sample_start':skip_bytes//2+i*window_samples,
                        'mean_centered':float(x.mean()-127.5), 'std':float(x.std()),
                        'max_symbol_fraction':top,'marginal_min_entropy':-math.log2(top),
                        'acf1':float(np.dot(y[:-1],y[1:])/den) if den else 1.0,
                        'clipped_fraction':float(np.mean((x==0)|(x==255)))})
    # Last half used as a descriptive reference only, not a trusted stable baseline.
    tail=windows[n//2:]
    features=('std','max_symbol_fraction','acf1','clipped_fraction')
    reference={k:float(np.median([w[k] for w in tail])) for k in features}
    # Simple relative change metrics, no arbitrary pass/fail or automatic trimming.
    for w in windows:
        w['difference_from_tail_reference']={k:float(w[k]-reference[k]) for k in features}
    return {'status':'EXPLORATORY_NOT_VALIDATED','channel':channel,'input_file':str(path),
            'max_bytes':max_bytes,'skip_bytes':skip_bytes,'window_samples':window_samples,
            'reference':'median of last half of windows (descriptive only)',
            'reference_values':reference,'windows':windows,
            'warnings':['No automatic startup trimming or health-test pass/fail decision',
                        'Reference tail may itself contain drift or interference',
                        'Marginal min-entropy is not conditional entropy or an extraction budget']}


def plot_transients(report, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from pathlib import Path
    w=report['windows']
    x=[a['index'] for a in w]
    fig,axs=plt.subplots(3,1,figsize=(10,8),sharex=True)
    for ax,key,title in zip(axs,['std','max_symbol_fraction','acf1'],
                            ['Standard deviation','Maximum symbol fraction','Lag-one autocorrelation']):
        ax.plot(x,[a[key] for a in w],linewidth=1)
        ax.axhline(report['reference_values'][key],linestyle='--',linewidth=1)
        ax.set_ylabel(title)
        ax.grid(alpha=.2)
    axs[-1].set_xlabel('Window index')
    fig.suptitle('Virgo-RNG transient diagnostics — exploratory, not validated')
    fig.tight_layout()
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=130);plt.close(fig)
