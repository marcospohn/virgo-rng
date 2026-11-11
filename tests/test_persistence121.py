import numpy as np
import pytest
from virgo_rng.persistence121 import analyze


def test_persistence(tmp_path):
    rng=np.random.default_rng(42)
    i=rng.integers(0,256,8192,dtype=np.uint8)
    q=np.roll(i,8)
    data=np.empty(2*len(i),dtype=np.uint8);data[::2]=i;data[1::2]=q
    path=tmp_path/'sample.cu8';path.write_bytes(data.tobytes())
    report=analyze(path,tmp_path/'out',windows=8,pairs=512)
    assert report['parameters']['windows_used']==8
    assert len(report['windows'])==8
    assert report['summary']['cross_minus8']['mean']>0.8
    assert (tmp_path/'out/persistence_report.json').exists()


def test_reject_short(tmp_path):
    p=tmp_path/'short.cu8';p.write_bytes(b'\0'*100)
    with pytest.raises(ValueError): analyze(p,tmp_path/'out')
