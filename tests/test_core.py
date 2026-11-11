import numpy as np
import pytest
from virgo_rng.core import analyze

def test_analyze():
    raw = np.random.default_rng(123).integers(0, 256, 8192, dtype=np.uint8).tobytes()
    result = analyze(raw)
    assert result['samples_iq'] == 4096
    assert len(result['acf_i']) == 16
    assert 0 <= result['marginal_min_entropy_bits_per_byte_unvalidated'] <= 8

def test_invalid():
    with pytest.raises(ValueError):
        analyze(b'abc')
