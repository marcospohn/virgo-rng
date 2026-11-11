import numpy as np
import pytest
from virgo_rng.temporal_dependence110 import analyze_file

def test_constant(tmp_path):
    raw=np.tile(np.array([128,128],dtype=np.uint8),2000)
    f=tmp_path/'a.cu8';f.write_bytes(raw.tobytes())
    r=analyze_file(f,out_dir=tmp_path/'out',rate=2000,window_seconds=1,sample_pairs=2000,plot=False)
    assert r['windows_analyzed']==1
    assert r['windows'][0]['i_given_previous_i_bits']==0
    assert r['windows'][0]['coarse_joint_iq_given_previous_joint_bits']==0

def test_reject_odd(tmp_path):
    f=tmp_path/'a.cu8';f.write_bytes(b'abc')
    with pytest.raises(ValueError):analyze_file(f,out_dir=tmp_path/'out',rate=2000,sample_pairs=1000,plot=False)
