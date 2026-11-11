#!/usr/bin/env python3
"""Virgo-RNG: ganhos de log-loss por janela e bootstrap exploratorio.
Requer previsor_pesos_virgo.py no mesmo diretorio.
Nao estima min-entropia ou significancia entre sessoes independentes.
"""
import argparse, csv, json
from pathlib import Path
import numpy as np
from previsor_pesos_virgo import get_data, features, fit, score, NAMES

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,default=Path('results/controlled_abab'))
    p.add_argument('--previous',type=Path,default=Path('results/pesos_multivariados/pesos.csv'))
    p.add_argument('--out',type=Path,default=Path('results/incerteza_pesos'))
    p.add_argument('--rate',type=int,default=2400000)
    p.add_argument('--seconds',type=int,default=180)
    p.add_argument('--windows',type=int,default=90)
    p.add_argument('--pairs',type=int,default=16384)
    p.add_argument('--alpha',type=float,default=32.)
    p.add_argument('--bootstraps',type=int,default=2000)
    p.add_argument('--block-windows',type=int,default=5)
    p.add_argument('--seed',type=int,default=20261028)
    args=p.parse_args()
    if not (1<=args.windows<=args.seconds and args.pairs>=10 and args.rate>=args.pairs+2 and args.alpha>0 and args.bootstraps>=100 and 1<=args.block_windows<=args.windows):
        p.error('Parametros invalidos')
    with args.previous.open(newline='') as f: previous=list(csv.DictReader(f))
    if len(previous)!=16: raise ValueError('Esperadas 16 linhas no pesos.csv original')
    args.out.mkdir(parents=True,exist_ok=True)
    data={name:get_data(args.data_dir/(name+'.cu8'),args.rate,args.seconds,args.windows,args.pairs) for name in NAMES}
    # Refit the same models; the previously selected weights are NOT retuned on test data.
    fitted={}
    for row in previous:
        key=(row['channel'],row['train'])
        if key not in fitted:
            fitted[key]=fit(*features(data[row['train']],row['channel']),args.alpha)
    rng=np.random.default_rng(args.seed)
    windows_out=[]; summary=[]
    for row in previous:
        channel,train,test=row['channel'],row['train'],row['test']
        weight=float(row['cross_weight'])
        lp,delta=fitted[(channel,train)]
        gains=[]
        for index,window in enumerate(data[test]):
            y,x=features([window],channel)
            baseline,_=score(y,x,lp,delta,0.)
            multi,_=score(y,x,lp,delta,weight)
            gain=baseline-multi
            gains.append(gain)
            windows_out.append({'channel':channel,'train':train,'validation':row['validation'],'test':test,'window_index':index,'second':int(np.linspace(0,args.seconds-1,args.windows,dtype=int)[index]),'cross_weight':weight,'baseline_bits':baseline,'multivariate_bits':multi,'improvement_bits':gain})
        gains=np.asarray(gains)
        # Moving block bootstrap of sampled windows, conditional on these four captures.
        starts=np.arange(args.windows-args.block_windows+1)
        reps=np.empty(args.bootstraps)
        for b in range(args.bootstraps):
            indices=[]
            while len(indices)<args.windows:
                s=int(rng.choice(starts))
                indices.extend(range(s,s+args.block_windows))
            reps[b]=float(gains[np.asarray(indices[:args.windows])].mean())
        lower,upper=np.quantile(reps,[.025,.975])
        summary.append({'channel':channel,'train':train,'validation':row['validation'],'test':test,'cross_weight':weight,'mean_gain_bits':float(gains.mean()),'median_gain_bits':float(np.median(gains)),'positive_windows':int(np.sum(gains>0)),'total_windows':len(gains),'ci_95_lower':float(lower),'ci_95_upper':float(upper),'bootstrap_block_windows':args.block_windows})
        print(f'{channel} {train} -> {test}: mean={gains.mean():+.7f}, positive={np.sum(gains>0)}/{len(gains)}, CI=[{lower:+.7f},{upper:+.7f}]',flush=True)
    for filename,rows in [('janelas.csv',windows_out),('resumo.csv',summary)]:
        with (args.out/filename).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    # Group by unique test capture and channel: avoid counting reused test data as independent replicates.
    per_capture=[]
    for test in NAMES:
        for channel in ('I','Q'):
            r=[x for x in summary if x['test']==test and x['channel']==channel]
            per_capture.append({'test':test,'channel':channel,'mean_gain_over_reused_models':float(np.mean([x['mean_gain_bits'] for x in r])),'models':len(r)})
    report={'settings':{'windows':args.windows,'pairs':args.pairs,'alpha':args.alpha,'bootstrap_repetitions':args.bootstraps,'bootstrap_block_windows':args.block_windows,'seed':args.seed},'summary':summary,'per_capture':per_capture,'limitations':['Bootstrap conditional on existing captures; not a confidence interval over independent acquisition sessions.','Windows sampled at separate seconds; block bootstrap over sampled windows is exploratory.','Same test captures are reused across models and must not be counted as independent experimental replicates.','Cross weights are read from previous pesos.csv and not retuned.','Log-loss improvement is not a min-entropy bound.']}
    (args.out/'incerteza.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Relatorios em',args.out)
if __name__=='__main__':main()
