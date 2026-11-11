import hashlib
import json
import numpy as np
import pytest
from virgo_rng.analysis import analyze_file
from virgo_rng.extract import condition_file

def test_analysis(tmp_path):
    f=tmp_path/'a.cu8'; data=np.tile(np.array([125,129,126,128],dtype=np.uint8),200)
    f.write_bytes(data.tobytes())
    r=analyze_file(f,max_lag=4,max_samples=300)
    assert r['samples_iq_total']==400
    assert r['samples_iq_diagnostic_window']==300
    assert r['histogram_all_bytes'][125]==200
    assert r['sha256_raw']==hashlib.sha256(f.read_bytes()).hexdigest()
    assert r['iq_pearson_r'] is not None

def test_conditioning(tmp_path):
    f=tmp_path/'in.cu8';o=tmp_path/'out.bin';f.write_bytes(bytes(range(256))*32)
    r=condition_file(f,o,4096)
    assert r['blocks']==2 and o.stat().st_size==64
    assert condition_file(f,o,4096)==r

def test_reject_odd(tmp_path):
    f=tmp_path/'odd.cu8';f.write_bytes(b'\x00'*513)
    with pytest.raises(ValueError):analyze_file(f)
