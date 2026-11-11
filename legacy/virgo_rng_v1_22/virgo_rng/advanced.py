"""Exploratory spectral and conditional-prediction diagnostics; no security guarantees."""
from pathlib import Path
import numpy as np
from .analysis import write_json

def diagnose(path, sample_rate=2400000, fft_size=4096, max_pairs=1000000):
    if sample_rate <= 0 or fft_size < 64 or fft_size & (fft_size - 1):
        raise ValueError('sample rate must be positive and fft size a power of two >= 64')
    if max_pairs < fft_size * 2:
        raise ValueError('max_pairs too small')
    path = Path(path)
    if path.stat().st_size % 2:
        raise ValueError('cu8 file must have even byte count')
    with path.open('rb') as f:
        raw = np.frombuffer(f.read(2 * max_pairs), dtype=np.uint8)
    if raw.size < fft_size * 4:
        raise ValueError('not enough IQ samples')
    i = raw[::2].astype(np.float32) - 127.5
    q = raw[1::2].astype(np.float32) - 127.5
    x = i + 1j*q
    blocks = len(x)//fft_size
    x = x[:blocks*fft_size].reshape(blocks,fft_size)
    x = x - x.mean(axis=1,keepdims=True)
    spectrum = np.fft.fftshift(np.fft.fft(x*np.hanning(fft_size),axis=1),axes=1)
    power = np.mean(np.abs(spectrum)**2,axis=0)
    db = 10*np.log10(np.maximum(power,1e-20))
    med = float(np.median(db))
    peak = float(np.max(db))
    # Non-IID diagnostic: naive one-step prediction from previous raw I byte,
    # evaluated on a chronological held-out segment (not an entropy bound).
    values = raw[::2]
    split = int(len(values)*0.7)
    train_prev = values[:split-1].astype(np.int32)
    train_next = values[1:split].astype(np.int32)
    joint = np.bincount(train_prev*256+train_next,minlength=65536).reshape(256,256)
    predictor = np.argmax(joint,axis=1)
    test_prev = values[split:-1]
    test_next = values[split+1:]
    accuracy = float(np.mean(predictor[test_prev] == test_next))
    counts = np.bincount(values[:split],minlength=256)
    baseline = float(np.max(counts)/counts.sum())
    return {'file':str(path),'sample_rate_sps':sample_rate,'fft_size':fft_size,
            'iq_pairs_analyzed':int(len(raw)//2),'frequency_offsets_hz':np.fft.fftshift(np.fft.fftfreq(fft_size,1/sample_rate)).tolist(),
            'power_db_relative':db.tolist(),'median_power_db_relative':med,
            'peak_above_median_db':peak-med,'bins_above_median_plus_10db':int(np.sum(db>med+10)),
            'prediction_i_next_byte_accuracy':accuracy,'prediction_i_constant_baseline':baseline,
            'security_status':'EXPLORATORY ONLY: prediction accuracy and PSD are NOT NIST SP 800-90B entropy estimates'}

def plot_report(report, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,4))
    ax.plot(np.array(report['frequency_offsets_hz'])/1000,report['power_db_relative'],lw=.8)
    ax.set(xlabel='Offset from center (kHz)',ylabel='Relative power (dB)',title='Virgo-RNG: diagnostic spectrum')
    fig.tight_layout();Path(output).parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=150);plt.close(fig)
