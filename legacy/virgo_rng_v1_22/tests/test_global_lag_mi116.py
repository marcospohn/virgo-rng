import numpy as np
import pytest
from virgo_rng.global_lag_mi116 import global_test

def test_global_output(tmp_path):
    rng=np.random.default_rng(42)
    raw=rng.integers(0,256,size=(6000,2),dtype=np.uint8)
    f=tmp_path/'test.cu8';f.write_bytes(raw.tobytes())
    r=global_test(f,out_dir=tmp_path/'out',rate=2000,window_seconds=1,
        sample_pairs=1000,windows=3,max_lag=3,permutations=19,plot=False)
    assert len(r['lags'])==7
    assert 0<r['global_test']['p_value_max_statistic']<=1
    assert (tmp_path/'out/global_lag_mi_report.json').exists()

def test_invalid(tmp_path):
    f=tmp_path/'a';f.write_bytes(b'123')
    with pytest.raises(ValueError):
        global_test(f,out_dir=tmp_path/'out',rate=2000,window_seconds=1,
                    sample_pairs=1000,windows=2,max_lag=3,permutations=19,plot=False)
