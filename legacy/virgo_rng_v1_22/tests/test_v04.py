import numpy as np
import pytest
from virgo_rng.advanced import diagnose

def test_advanced(tmp_path):
    p=tmp_path/'data.cu8'
    np.random.default_rng(1).integers(0,256,size=65536,dtype=np.uint8).tofile(p)
    r=diagnose(p,fft_size=256,max_pairs=20000)
    assert len(r['frequency_offsets_hz'])==256
    assert 0<=r['prediction_i_next_byte_accuracy']<=1
    assert r['peak_above_median_db']>=0

def test_invalid_fft(tmp_path):
    p=tmp_path/'data.cu8';p.write_bytes(b'\x00'*4096)
    with pytest.raises(ValueError): diagnose(p,fft_size=300)
