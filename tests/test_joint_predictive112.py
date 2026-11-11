import numpy as np
import pytest
from virgo_rng.joint_predictive112 import evaluate, analyze_file


def test_iq_joint_predictable():
    rng=np.random.default_rng(12)
    x=rng.integers(0,16,10000,dtype=np.uint8)
    x[1:]=x[0]  # deterministic series, easy to predict
    metrics=evaluate(x)
    assert metrics[1]['gain_vs_baseline_bits']>=-0.01
    assert metrics[1]['cross_entropy_bits']<0.1


def test_iq_joint_random():
    x=np.random.default_rng(123).integers(0,16,10000,dtype=np.uint8)
    scores=evaluate(x)
    assert len(scores)==5
    assert all(np.isfinite(r['cross_entropy_bits']) for r in scores)


def test_joint_file(tmp_path):
    rng=np.random.default_rng(6)
    data=rng.integers(0,256,size=(3000,2),dtype=np.uint8)
    path=tmp_path/'x.cu8';path.write_bytes(data.tobytes())
    out=tmp_path/'out'
    report=analyze_file(path,out_dir=out,rate=3000,sample_pairs=2000,windows=1,shuffle_repeats=2,plot=False)
    assert report['alphabet_size']==16
    assert len(report['windows'])==1
    assert (out/'joint_predictive_report.json').exists()


def test_odd_file_rejected(tmp_path):
    path=tmp_path/'bad.cu8';path.write_bytes(b'abc')
    with pytest.raises(ValueError,match='Incomplete'):
        analyze_file(path,out_dir=tmp_path/'out',rate=1000,sample_pairs=1000,plot=False)
