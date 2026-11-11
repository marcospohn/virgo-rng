"""Auditoria retrospectiva de dois relatórios global-lag-mi (sem recalcular permutações)."""
import json
from pathlib import Path


def audit_reports(discovery, replication, output):
    a=json.loads(Path(discovery).read_text()); b=json.loads(Path(replication).read_text())
    if a.get('schema')!='virgo-rng-global-lag-mi-v1' or b.get('schema')!='virgo-rng-global-lag-mi-v1':
        raise ValueError('Ambos devem ser relatórios global-lag-mi-v1')
    for name,r in [('discovery',a),('replication',b)]:
        n=len(r['lags'])
        if n!=len(r['excess_mi_bits']) or n!=len(r['pointwise_p_uncorrected']):
            raise ValueError(f'Comprimentos inconsistentes em {name}')
        if len(set(r['lags']))!=n: raise ValueError('Defasagens duplicadas')
    if a['lags']!=b['lags'] or a['quantization_bits_per_component']!=b['quantization_bits_per_component'] or a['sample_pairs_per_window']!=b['sample_pairs_per_window']:
        raise ValueError('Parâmetros incompatíveis: não comparar diretamente')
    targets=(-8,8)
    rows=[]
    for lag in targets:
        x=a['lags'].index(lag); y=b['lags'].index(lag)
        rows.append({'lag':lag,'discovery_excess_bits':a['excess_mi_bits'][x],
                     'replication_excess_bits':b['excess_mi_bits'][y],
                     'replication_pointwise_p':b['pointwise_p_uncorrected'][y]})
    # Holm step-down controls FWER for two prespecified tests if the p-values are valid.
    ordered=sorted(rows,key=lambda r:r['replication_pointwise_p'])
    running=0
    for rank,row in enumerate(ordered):
        running=max(running,min(1.,(len(ordered)-rank)*row['replication_pointwise_p']))
        row['holm_adjusted_p_two_lags']=running
        row['passes_0_05_if_null_valid']=running<=0.05
    output_data={'schema':'virgo-rng-audit-v1','discovery':str(discovery),'replication':str(replication),
                 'prespecified_lags':list(targets),'lag_results':sorted(rows,key=lambda r:r['lag']),
                 'global_tests':{'discovery':a['global_test'],'replication':b['global_test']},
                 'null_95_ratio_replication_over_discovery':b['global_test']['null_max_95th_percentile_bits']/a['global_test']['null_max_95th_percentile_bits'],
                 'interpretation':'Exploratory audit only: Holm-adjusted pointwise p-values are conditional on valid circular-shift null and valid pre-registration of +/-8 before replication.',
                 'limitations':['No raw permutation distribution in existing JSON; cannot independently verify p-values or null exchangeability.',
                                'Same permutation seed across captures is not by itself evidence of invalidity.',
                                'Shared nonstationarity or periodic interference may invalidate circular-shift controls.',
                                'No claim of physical coupling, independent entropy, or cryptographic min-entropy.',
                                'First capture selected the lags; only second capture is eligible for a pre-specified two-lag confirmation.']}
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(output_data,indent=2,ensure_ascii=False)+'\n')
    return output_data


def main():
    import argparse
    p=argparse.ArgumentParser(description='Audit discovery and replication global-lag-mi JSON')
    p.add_argument('discovery');p.add_argument('replication');p.add_argument('--out',default='results/audit117/audit_report.json')
    args=p.parse_args();r=audit_reports(args.discovery,args.replication,args.out)
    print(json.dumps({'report':args.out,'lag_results':r['lag_results'],'null_95_ratio':r['null_95_ratio_replication_over_discovery']},indent=2))

if __name__=='__main__': main()
