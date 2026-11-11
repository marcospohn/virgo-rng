import numpy as np
import pytest
from virgo_rng.research09 import predictor_histories,change_diagnostics,campaign_summary,research_report
from virgo_rng.validation import save_report

def test_predictors():
    a=np.tile(np.array([11,23,37,42],dtype=np.uint8),1000)
    result=predictor_histories(a)
    assert result[1]['accuracy']>.99
    assert result[0]['accuracy']<.3

def test_change_flags():
    w=[{'std':10.0+i*.01,'acf1':.1,'max_symbol_fraction':.03} for i in range(20)]
    w[0]['std']=100
    assert 0 in change_diagnostics(w)['flagged_windows']

def test_invalid_history():
    with pytest.raises(ValueError):predictor_histories(np.arange(2000,dtype=np.uint16).astype('uint8'),histories=(4,))

def test_report_and_campaign(tmp_path):
    f=tmp_path/'in.cu8';rng=np.random.default_rng(7)
    f.write_bytes(rng.integers(0,256,40000,dtype=np.uint8).tobytes())
    r=research_report(f,max_bytes=40000,window_samples=1024)
    p=tmp_path/'report.json';save_report(p,r)
    assert len(campaign_summary([p])['campaigns'])==1
