import numpy as np
import pytest
from virgo_rng.validation import window_diagnostics, binary_tests, conditional_predictor, plot_windows

def test_predictor_detects_determinism():
    a=np.zeros(4096,dtype=np.uint8)
    result=conditional_predictor(a)
    assert result['accuracy']==1

def test_predictor_handles_unseen_states():
    a=np.concatenate([np.zeros(2000,dtype=np.uint8),np.ones(2000,dtype=np.uint8)])
    result=conditional_predictor(a)
    assert 0 <= result['accuracy'] <= 1

def test_window_report(tmp_path):
    p=tmp_path/'a.cu8'
    rng=np.random.default_rng(11)
    p.write_bytes(rng.integers(0,256,8192,dtype=np.uint8).tobytes())
    r=window_diagnostics(p,max_bytes=8192,window_samples=512)
    assert len(r['windows'])==8
    assert r['status'].startswith('EXPLORATORY')

def test_skip_validation(tmp_path):
    p=tmp_path/'a.cu8';p.write_bytes(bytes(4096))
    with pytest.raises(ValueError): window_diagnostics(p,skip_bytes=1)

def test_binary_zero_detection(tmp_path):
    p=tmp_path/'zeros.bin';p.write_bytes(bytes(128))
    r=binary_tests(p)
    assert r['one_fraction']==0 and r['frequency_two_sided_p_approx'] < 0.01

def test_binary_short(tmp_path):
    p=tmp_path/'short.bin';p.write_bytes(bytes(2))
    with pytest.raises(ValueError):binary_tests(p)
