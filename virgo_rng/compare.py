"""Compare two cu8 acquisitions using existing offline diagnostics."""
from .analysis import analyze_file

def compare_files(a,b,max_lag=64,window_samples=1000000):
    x=analyze_file(a,max_lag,window_samples);y=analyze_file(b,max_lag,window_samples)
    metrics=['mean_i','mean_q','std_i','std_q','iq_pearson_r','clipped_fraction','marginal_min_entropy_bits_per_byte_unvalidated']
    return {'first':str(a),'second':str(b),'first_sha256':x['sha256_raw'],'second_sha256':y['sha256_raw'],
            'metrics':{k:{'first':x[k],'second':y[k],'difference_second_minus_first':(y[k]-x[k]) if x[k] is not None and y[k] is not None else None} for k in metrics},
            'acf_i_first':x['acf_i'],'acf_i_second':y['acf_i'],
            'acf_q_first':x['acf_q'],'acf_q_second':y['acf_q'],
            'status':'DESCRIPTIVE comparison only; not proof of astronomical entropy or source security'}
