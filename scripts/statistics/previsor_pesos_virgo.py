#!/usr/bin/env python3
"""Virgo-RNG: validação de contribuição cruzada I/Q, entre capturas.
Não fornece min-entropia certificada nem teste NIST SP 800-90B.
"""
import argparse, csv, json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar

NAMES = ('A1_50ohm','B1_antenna','A2_50ohm','B2_antenna')
LAGS = (1,2)

def get_data(path, rate, seconds, windows, pairs):
    raw = np.memmap(path, dtype='u1', mode='r')
    expected = 2 * rate * seconds
    if raw.size != expected:
        raise ValueError(f'{path}: {raw.size} bytes, expected {expected}')
    positions = np.linspace(0, seconds-1, windows, dtype=int)
    if len(np.unique(positions)) != windows:
        raise ValueError('More windows than seconds')
    chunks=[]
    for sec in positions:
        start = 2*rate*int(sec)
        chunk = np.array(raw[start:start+2*(pairs+max(LAGS))], copy=True)
        if chunk.size != 2*(pairs+max(LAGS)):
            raise ValueError(f'Incomplete window in {path}')
        chunks.append((chunk[::2],chunk[1::2]))
    return chunks

def features(chunks, channel):
    ys=[]; xs={f'{kind}{lag}':[] for kind in ('own','cross') for lag in LAGS}
    for i,q in chunks:
        own,other=(i,q) if channel=='I' else (q,i)
        ys.append(own[2:])
        for lag in LAGS:
            xs[f'own{lag}'].append(own[2-lag:len(own)-lag])
            xs[f'cross{lag}'].append(other[2-lag:len(other)-lag])
    return np.concatenate(ys),{k:np.concatenate(v) for k,v in xs.items()}

def fit(y,x,alpha):
    freq=np.bincount(y,minlength=256).astype(float)+alpha
    prior=freq/freq.sum(); lp=np.log(prior)
    delta={}
    for key,v in x.items():
        joint=np.bincount(v.astype(np.int32)*256+y.astype(np.int32),minlength=65536).reshape(256,256).astype(float)
        joint+=alpha*prior[None,:]
        p=joint/joint.sum(axis=1,keepdims=True)
        delta[key]=np.log(p)-lp[None,:]
    return lp,delta

def score(y,x,lp,delta,cross_weight,chunk=1024):
    # Fixed own-channel weights (0.5 each); cross-channel weight is learned
    # on a different capture, with zero allowed (nested baseline).
    total=0.; correct=0
    for a in range(0,len(y),chunk):
        b=min(a+chunk,len(y)); n=b-a
        z=np.broadcast_to(lp,(n,256)).copy()
        z+=0.5*delta['own1'][x['own1'][a:b]]
        z+=0.5*delta['own2'][x['own2'][a:b]]
        if cross_weight:
            z+=cross_weight*0.5*(delta['cross1'][x['cross1'][a:b]]+delta['cross2'][x['cross2'][a:b]])
        m=z.max(axis=1)
        norm=m+np.log(np.exp(z-m[:,None]).sum(axis=1))
        total+=float(np.sum(norm-z[np.arange(n),y[a:b]]))
        correct+=int(np.count_nonzero(np.argmax(z,axis=1)==y[a:b]))
    return total/len(y)/np.log(2),correct/len(y)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,default=Path('results/controlled_abab'))
    p.add_argument('--out',type=Path,default=Path('results/pesos_multivariados'))
    p.add_argument('--rate',type=int,default=2400000)
    p.add_argument('--seconds',type=int,default=180)
    p.add_argument('--windows',type=int,default=90)
    p.add_argument('--pairs',type=int,default=16384)
    p.add_argument('--alpha',type=float,default=32.)
    args=p.parse_args()
    if args.seconds<1 or not (1<=args.windows<=args.seconds) or args.pairs<10 or args.rate<args.pairs+2 or args.alpha<=0:
        p.error('Invalid parameters')
    args.out.mkdir(parents=True,exist_ok=True)
    datasets={n:get_data(args.data_dir/(n+'.cu8'),args.rate,args.seconds,args.windows,args.pairs) for n in NAMES}
    # Validation is an independent capture, of the same RF condition as training.
    # Test captures are both from the opposite condition and never used for fitting/tuning.
    folds=[('A1_50ohm','A2_50ohm',['B1_antenna','B2_antenna']),
           ('A2_50ohm','A1_50ohm',['B1_antenna','B2_antenna']),
           ('B1_antenna','B2_antenna',['A1_50ohm','A2_50ohm']),
           ('B2_antenna','B1_antenna',['A1_50ohm','A2_50ohm'])]
    rows=[]
    for channel in ('I','Q'):
        d={n:features(chunks,channel) for n,chunks in datasets.items()}
        for train,valid,tests in folds:
            lp,delta=fit(*d[train],args.alpha)
            vy,vx=d[valid]
            # optimize cross-channel coefficient only; baseline coefficient zero included.
            opt=minimize_scalar(lambda w:score(vy,vx,lp,delta,float(w))[0],bounds=(0,2),method='bounded',options={'xatol':0.01})
            candidates=[(0.,score(vy,vx,lp,delta,0.)[0]),(float(opt.x),float(opt.fun))]
            weight=min(candidates,key=lambda v:v[1])[0]
            for test in tests:
                ty,tx=d[test]
                base,acc0=score(ty,tx,lp,delta,0.)
                multi,acc1=score(ty,tx,lp,delta,weight)
                row={'channel':channel,'train':train,'validation':valid,'test':test,
                     'cross_weight':weight,'baseline_bits':base,'multivariate_bits':multi,
                     'improvement_bits':base-multi,'baseline_accuracy':acc0,
                     'multivariate_accuracy':acc1,'test_symbols':len(ty)}
                rows.append(row)
                print(f'{channel} {train} -> {test}: weight={weight:.3f}, delta={base-multi:+.6f} bits/byte',flush=True)
    with (args.out/'pesos.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    report={'settings':{'windows':args.windows,'pairs':args.pairs,'sample_fraction':args.windows*args.pairs/(args.seconds*args.rate),'alpha':args.alpha},
            'method':'Train on one capture, tune nonnegative cross weight on a second same-condition capture, test on opposite-condition captures. Own lag 1 and 2 weights fixed at 0.5 each.',
            'limitations':['Only selected windows are sampled','Averaging dependent windows does not create independent hardware replicates','Conditional log-loss is not a validated min-entropy bound','Fixed own weights and additive model do not capture arbitrary interactions'],
            'rows':rows}
    (args.out/'pesos.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print('Saved',args.out/'pesos.csv',args.out/'pesos.json')
if __name__=='__main__':main()
