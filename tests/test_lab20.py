import json
import numpy as np
import pytest
from virgo_rng.lab20 import DEFAULT, config_load, study, sha256

def test_defaults():
    assert config_load(None)==DEFAULT

def test_reject_invalid_config(tmp_path):
    f=tmp_path/'bad.json';f.write_text('{"unexpected": 1}')
    with pytest.raises(ValueError):config_load(f)

def test_reject_odd_cu8(tmp_path):
    f=tmp_path/'odd.cu8';f.write_bytes(b'abc')
    with pytest.raises(ValueError):study(f,tmp_path/'out',DEFAULT)

def test_study_provenance_and_no_overwrite(tmp_path):
    f=tmp_path/'signal.cu8'
    rng=np.random.default_rng(41)
    f.write_bytes(rng.integers(0,256,size=4096*2,dtype=np.uint8).tobytes())
    cfg=DEFAULT.copy();cfg.update(pairs_per_window=512,windows=4,lags=[8,41],max_analysis_bytes=4096)
    out=tmp_path/'out'
    rep=study(f,out,cfg)
    assert rep['status']=='completed'
    assert rep['input_sha256']==sha256(f)
    assert rep['steps']['persistence']['coverage']['fraction_of_file']==0.5
    assert (out/'descriptive_entropy.json').is_file()
    with pytest.raises(ValueError):study(f,out,cfg)
