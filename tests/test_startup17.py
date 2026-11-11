import numpy as np
from pathlib import Path
from virgo_rng.startup16 import analyze_capture

def test_all_64_blocks(tmp_path):
    p=tmp_path/'sample.cu8'
    rng=np.random.default_rng(7)
    p.write_bytes(rng.integers(0,256,size=262144*2,dtype=np.uint8).tobytes())
    result=analyze_capture(p)
    assert result['blocks_analyzed']==64
    assert len(result['channels']['i']['blocks'])==64
    assert 'shannon_bits' in result['channels']['q']['first_vs_rest']

def test_optional_block_cap(tmp_path):
    p=tmp_path/'sample.cu8'; p.write_bytes(bytes(range(256))*4096)
    assert analyze_capture(p,block_pairs=4096,max_blocks=4)['blocks_analyzed']==4
