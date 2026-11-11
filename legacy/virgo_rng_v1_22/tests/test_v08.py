import numpy as np
import pytest
from virgo_rng.transients import transient_report

def test_transient_diagnostic(tmp_path):
    rng=np.random.default_rng(42)
    a=rng.integers(0,256,size=(4096*8,2),dtype=np.uint8)
    a[:4096,0]=127
    path=tmp_path/'test.cu8';path.write_bytes(a.tobytes())
    report=transient_report(path,max_bytes=a.nbytes,window_samples=4096)
    assert len(report['windows'])==8
    assert report['windows'][0]['std']==0
    assert report['windows'][0]['max_symbol_fraction']==1
    assert report['windows'][1]['std']>0
    assert report['status']=='EXPLORATORY_NOT_VALIDATED'

def test_short_file(tmp_path):
    p=tmp_path/'x.cu8';p.write_bytes(b'\x00\x00'*512)
    with pytest.raises(ValueError): transient_report(p)
