import numpy as np
import pytest
from virgo_rng.spectral120 import analyze

def test_iq_spectral(tmp_path):
    rng=np.random.default_rng(120)
    i=rng.integers(50,200,16384,dtype=np.uint8)
    q=i.copy()
    data=np.empty(32768,dtype=np.uint8);data[::2]=i;data[1::2]=q
    f=tmp_path/'test.cu8';f.write_bytes(data.tobytes())
    r=analyze(f,tmp_path/'out',pairs=8192,fft_size=256,windows=2,max_lag=16)
    assert r['cross_correlation_iq'][16]>0.999
    assert np.mean(r['magnitude_squared_coherence'])>0.99
    assert (tmp_path/'out'/'spectral_report.json').exists()

def test_reject_invalid(tmp_path):
    f=tmp_path/'x.cu8';f.write_bytes(b'\x7f\x80'*100)
    with pytest.raises(ValueError): analyze(f,tmp_path/'out',pairs=1024,fft_size=256)
