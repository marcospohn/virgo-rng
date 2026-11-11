import numpy as np
from virgo_rng.health import health_file
from virgo_rng.compare import compare_files

def test_health_detects_constant(tmp_path):
    p=tmp_path/'a.cu8';p.write_bytes(bytes([127])*2048)
    r=health_file(p,window_bytes=256,repetition_cutoff=16)
    assert r['max_identical_run']==2048
    assert r['repetition_alarm_count']==1
    assert r['proportion_alarm_windows']==8

def test_health_detects_run_across_windows(tmp_path):
    p=tmp_path/'a.cu8';p.write_bytes(bytes([1])*256+bytes([1])*256)
    assert health_file(p,256,32)['max_identical_run']==512

def test_health_empty(tmp_path):
    p=tmp_path/'empty';p.write_bytes(b'')
    try:health_file(p)
    except ValueError:pass
    else:assert False

def test_compare_identical(tmp_path):
    p=tmp_path/'a.cu8';p.write_bytes(np.tile(np.arange(256,dtype=np.uint8),8).tobytes())
    r=compare_files(p,p,4,256)
    assert all(v['difference_second_minus_first']==0 for v in r['metrics'].values() if v['difference_second_minus_first'] is not None)
