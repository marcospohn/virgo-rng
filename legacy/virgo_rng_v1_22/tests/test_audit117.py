import json
from virgo_rng.audit117 import audit_reports

def test_holm(tmp_path):
    d={'schema':'virgo-rng-global-lag-mi-v1','lags':[-8,0,8], 'excess_mi_bits':[.003,0,.003],
       'pointwise_p_uncorrected':[.02,.5,.015], 'quantization_bits_per_component':4,
       'sample_pairs_per_window':30000,'global_test':{'null_max_95th_percentile_bits':.003}}
    a=tmp_path/'a.json'; b=tmp_path/'b.json'; out=tmp_path/'out.json'
    a.write_text(json.dumps(d));b.write_text(json.dumps(d))
    r=audit_reports(a,b,out)
    assert out.exists()
    assert [v['holm_adjusted_p_two_lags'] for v in r['lag_results']]==[.03,.03]

def test_reject_incompatible(tmp_path):
    import pytest
    d={'schema':'virgo-rng-global-lag-mi-v1','lags':[-8,8],'excess_mi_bits':[.1,.2],
       'pointwise_p_uncorrected':[.01,.01],'quantization_bits_per_component':4,
       'sample_pairs_per_window':30000,'global_test':{'null_max_95th_percentile_bits':.003}}
    a=tmp_path/'a';b=tmp_path/'b';a.write_text(json.dumps(d));d['sample_pairs_per_window']=120000;b.write_text(json.dumps(d))
    with pytest.raises(ValueError):audit_reports(a,b,tmp_path/'out')
