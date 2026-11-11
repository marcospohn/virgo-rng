import numpy as np
import pytest
from virgo_rng.audit119 import _block_reorder, run

def test_reorder_preserves_each_block():
    q=np.arange(64)
    y=_block_reorder(q,8,np.random.default_rng(3))
    assert sorted(y.tolist())==list(q)
    assert all(np.all(np.diff(y[k:k+8])==1) for k in range(0,64,8))

def test_invalid_reorder():
    with pytest.raises(ValueError):_block_reorder(np.arange(63),8,np.random.default_rng(1))

def test_run_small(tmp_path):
    rng=np.random.default_rng(9)
    f=tmp_path/'tiny.cu8';f.write_bytes(rng.integers(0,256,size=2*4096,dtype=np.uint8).tobytes())
    r=run(f,tmp_path/'out',rate=1024,window_seconds=1,sample_pairs=512,windows=3,
          max_lag=8,bits=4,permutations=19,block_pairs=64,plot=False)
    assert r['schema']=='virgo-rng-local-audit-v119'
    assert len(r['lags'])==17
    assert (tmp_path/'out'/'local_null_profiles.npz').exists()
