import numpy as np
import pytest
from virgo_rng.dependence19 import analyze_file

def test_equal_channels(tmp_path):
    rng=np.random.default_rng(123)
    i=rng.integers(0,256,10000,dtype=np.uint8)
    a=np.column_stack((i,i))
    src=tmp_path/'x.cu8';src.write_bytes(a.tobytes())
    result=analyze_file(src,out_dir=tmp_path/'out',chunk_pairs=1024,max_lag=4,lag_pairs=500,plot=False)
    h=result['shannon_bits']
    assert abs(h['q_given_i'])<1e-9
    assert h['joint_iq']==pytest.approx(h['i'])
    assert result['cross_correlation_lag0']==pytest.approx(1)
    assert (tmp_path/'out'/'dependence_report.json').exists()

def test_independent_channels(tmp_path):
    rng=np.random.default_rng(42)
    a=rng.integers(0,4,size=(40000,2),dtype=np.uint8)
    src=tmp_path/'x.cu8';src.write_bytes(a.tobytes())
    h=analyze_file(src,out_dir=tmp_path/'out',plot=False,max_lag=2)['shannon_bits']
    assert h['mutual_information']<0.01
    assert h['joint_iq']>3.98

def test_odd_bytes(tmp_path):
    src=tmp_path/'x.cu8';src.write_bytes(b'123')
    with pytest.raises(ValueError):analyze_file(src,out_dir=tmp_path/'out',plot=False)
