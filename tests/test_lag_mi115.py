import numpy as np
import pytest
from virgo_rng.lag_mi115 import lagged_mi,mutual_information,analyze_file

def test_independent_low_mi():
    rng=np.random.default_rng(115)
    a=rng.integers(0,16,100000,dtype=np.uint8)
    b=rng.integers(0,16,100000,dtype=np.uint8)
    assert mutual_information(a,b,16)<0.01

def test_known_cross_lag():
    rng=np.random.default_rng(116)
    q=rng.integers(0,16,10000,dtype=np.uint8)
    i=np.roll(q,3)
    assert lagged_mi(i,q,3,16)>3.9
    assert lagged_mi(i,q,0,16)<0.1

def test_file(tmp_path):
    rng=np.random.default_rng(117)
    file=tmp_path/'data.cu8'
    file.write_bytes(rng.integers(0,256,12000,dtype=np.uint8).tobytes())
    r=analyze_file(file,out_dir=tmp_path/'out',rate=1000,window_seconds=2,sample_pairs=1000,windows=2,max_lag=4,quantization_bits=2,control_repeats=2,plot=False)
    assert len(r['lags'])==9
    assert len(r['windows'])==2
    assert (tmp_path/'out/lag_mi_report.json').exists()

def test_odd_file(tmp_path):
    f=tmp_path/'odd.cu8';f.write_bytes(b'123')
    with pytest.raises(ValueError):analyze_file(f,out_dir=tmp_path/'out',plot=False)
