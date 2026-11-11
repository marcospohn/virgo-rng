import numpy as np
import pytest
from virgo_rng.cross_channel114 import evaluate,analyze_file

def test_independent_channels():
    rng=np.random.default_rng(42)
    a=rng.integers(0,4,3000,dtype=np.uint8);b=rng.integers(0,4,3000,dtype=np.uint8)
    x=evaluate(a,b)
    assert set(x)=={'i','q'}
    assert all(np.isfinite(v['incremental_other_channel_gain_bits']) for v in x['i'])

def test_dependent_cross_history():
    rng=np.random.default_rng(5)
    q=rng.integers(0,4,10000,dtype=np.uint8)
    i=np.empty_like(q);i[0]=0;i[1:]=q[:-1]
    result=evaluate(i,q)
    assert result['i'][0]['incremental_other_channel_gain_bits']>0.3

def test_small_file(tmp_path):
    rng=np.random.default_rng(6)
    raw=rng.integers(0,256,12000,dtype=np.uint8)
    file=tmp_path/'x.cu8';file.write_bytes(raw.tobytes())
    r=analyze_file(file,out_dir=tmp_path/'out',rate=1000,window_seconds=2,sample_pairs=1000,windows=2,shuffle_repeats=2,plot=False)
    assert (tmp_path/'out/cross_channel_report.json').exists()
    assert len(r['windows'])==2

def test_odd_file(tmp_path):
    f=tmp_path/'x.cu8';f.write_bytes(b'123')
    with pytest.raises(ValueError):analyze_file(f,out_dir=tmp_path/'out',plot=False)
