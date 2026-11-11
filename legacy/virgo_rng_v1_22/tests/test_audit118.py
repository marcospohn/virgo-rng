import numpy as np
import pytest
from virgo_rng.audit118 import run

def test_null_audit(tmp_path):
    rng=np.random.default_rng(3)
    data=rng.integers(0,256,size=(12000,2),dtype=np.uint8)
    f=tmp_path/'test.cu8';f.write_bytes(data.tobytes())
    out=tmp_path/'out'
    r=run(f,out,rate=2000,window_seconds=1,sample_pairs=1000,windows=3,max_lag=8,bits=3,permutations=19,plot=False)
    assert r['schema']=='virgo-rng-null-audit-v118'
    assert (out/'null_profiles.npz').exists()
    with np.load(out/'null_profiles.npz') as x:
        assert x['wide_null_profiles'].shape==(19,17)
        assert x['half_turn_shifts'].shape==(19,3)
    for m in r['methods'].values():assert 0<m['p_global']<=1

def test_bad_input(tmp_path):
    f=tmp_path/'bad';f.write_bytes(b'abc')
    with pytest.raises(ValueError):run(f,tmp_path/'out',plot=False)
