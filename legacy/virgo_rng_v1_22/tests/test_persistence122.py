import numpy as np
from virgo_rng.persistence122 import analyze

def test_full_covers_complete_windows(tmp_path):
    rng=np.random.default_rng(122)
    n=512*5+19
    i=rng.integers(0,256,n,dtype=np.uint8)
    q=np.roll(i,8)
    a=np.empty(2*n,dtype=np.uint8);a[::2]=i;a[1::2]=q
    p=tmp_path/'x.cu8';p.write_bytes(a.tobytes())
    r=analyze(p,tmp_path/'full',pairs=512,full=True)
    assert r['parameters']['windows_used']==5
    assert r['coverage']['analyzed_pairs']==2560
    assert r['coverage']['unanalyzed_pairs']==19
    assert r['coverage']['fraction_of_file']==2560/n
    assert r['parameters']['mode']=='full'
    assert r['summary']['cross_minus8']['mean']>0.7
    s=analyze(p,tmp_path/'sparse',pairs=512,windows=3)
    assert s['parameters']['windows_used']==3
    assert s['windows'][-1]['start_seconds']>s['windows'][0]['start_seconds']
