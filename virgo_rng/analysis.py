"""Offline cu8 analysis; diagnostic only, not NIST 800-90B validation."""
import hashlib
import json
from pathlib import Path
import numpy as np

def analyze_file(path, max_lag=64, max_samples=1_000_000):
    path=Path(path)
    size=path.stat().st_size
    if size < 512 or size % 2:
        raise ValueError("cu8 file must contain at least 256 complete IQ pairs")
    if max_lag < 1 or max_samples < max_lag + 2:
        raise ValueError("invalid lag or sample limit")
    # Sample a contiguous window, preserving short-lag correlations. Stream entire file for histograms/hash.
    nbytes=min(size, 2*max_samples)
    with path.open('rb') as f:
        window=np.frombuffer(f.read(nbytes),dtype=np.uint8)
        counts=np.zeros(256,dtype=np.int64)
        h=hashlib.sha256()
        f.seek(0)
        while chunk:=f.read(4*1024*1024):
            h.update(chunk)
            counts+=np.bincount(np.frombuffer(chunk,dtype=np.uint8),minlength=256)
    i=window[::2].astype(np.float64)-127.5
    q=window[1::2].astype(np.float64)-127.5
    def acf(x):
        x=x-x.mean(); denom=float(np.dot(x,x))
        return [float(np.dot(x[:-lag],x[lag:])/denom) if denom else 0.0 for lag in range(1,max_lag+1)]
    def cross(x,y):
        sx=x.std();sy=y.std()
        return float(np.mean((x-x.mean())*(y-y.mean()))/(sx*sy)) if sx and sy else None
    pmax=int(counts.max())/size
    return {'format':'cu8','file_bytes':size,'samples_iq_total':size//2,
            'samples_iq_diagnostic_window':len(i),'mean_i':float(i.mean()),'mean_q':float(q.mean()),
            'std_i':float(i.std()),'std_q':float(q.std()),'iq_pearson_r':cross(i,q),
            'acf_i':acf(i),'acf_q':acf(q), 'histogram_all_bytes':counts.tolist(),
            'clipped_fraction':float((counts[0]+counts[255])/size),
            'marginal_min_entropy_bits_per_byte_unvalidated':float(-np.log2(pmax)),
            'sha256_raw':h.hexdigest(),
            'security_status':'EXPERIMENTAL ONLY: marginal entropy is not an entropy-rate bound; output is NOT cryptographically validated'}

def write_json(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
