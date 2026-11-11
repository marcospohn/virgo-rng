import numpy as np
import pytest
from virgo_rng.temporal18 import analyze_file

def test_temporal_file(tmp_path):
    f=tmp_path/'x.cu8'; a=np.arange(256,dtype=np.uint8);f.write_bytes(np.tile(a,8).tobytes())
    r=analyze_file(f,rate=128,window_pairs=128,output=tmp_path/'out',plot=False)
    assert r['windows_analyzed']==8
    assert r['trailing_pairs_not_analyzed']==0
    assert (tmp_path/'out'/'temporal_report.json').exists()

def test_incomplete_window(tmp_path):
    f=tmp_path/'x.cu8';f.write_bytes(b'\x00\x01')
    with pytest.raises(ValueError):analyze_file(f,window_pairs=100)
