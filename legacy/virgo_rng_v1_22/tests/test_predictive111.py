import numpy as np
from virgo_rng.predictive111 import _scores, analyze_file

def test_predictor_deterministic():
    x=np.tile(np.arange(16,dtype=np.uint8),2000)
    a=_scores(x,1,20000)
    assert a['predictive_gain_bits']>2.0
    assert a['test_unseen_context_fraction']==0

def test_predictor_independent():
    x=np.random.default_rng(4).integers(0,16,40000,dtype=np.uint8)
    a=_scores(x,1,28000)
    assert a['predictive_gain_bits']<0.03

def test_report(tmp_path):
    data=np.random.default_rng(1).integers(0,256,40000,dtype=np.uint8)
    p=tmp_path/'test.cu8';p.write_bytes(data.tobytes())
    r=analyze_file(p,out_dir=tmp_path/'out',rate=10000,sample_pairs=5000,windows=2,plot=False)
    assert len(r['windows'])==2
    assert (tmp_path/'out'/'predictive_report.json').exists()
    assert '8' in r['summary']['I']
