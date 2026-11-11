#!/usr/bin/env python3
"""E7: diagnostico temporal e estatistico, sem modificar CU8 originais.
Uso: python virgo_e7_analise_final.py --dir results/E7_carina
Dependencias: numpy (padrao do ambiente Virgo). Produz analysis_final/*.csv e *.json.
"""
import argparse,csv,json,math
from pathlib import Path
import numpy as np

NAMES=['A1','ON1','OFF1','ON2','OFF2','ON3','A2']
RATE=2400000; CENTER=1420405752; FFT=8192; TARGET=1420392000

def entropies(values):
    counts=np.bincount(values,minlength=256).astype(np.float64)
    p=counts[counts>0]/counts.sum()
    return float(-np.sum(p*np.log2(p))),float(-math.log2(p.max()))

def process_file(path,seconds,window_seconds=10):
    raw=np.memmap(path,dtype=np.uint8,mode='r')
    expected=2*RATE*seconds
    if raw.size!=expected: raise ValueError(f'{path.name}: esperado {expected} bytes, encontrado {raw.size}')
    f=CENTER+np.fft.fftshift(np.fft.fftfreq(FFT,d=1/RATE))
    band=np.abs(f-TARGET)<=20000
    side=((np.abs(f-(TARGET-60000))<=20000)|(np.abs(f-(TARGET+60000))<=20000))
    win=np.hanning(FFT).astype(np.float32)
    results=[]
    for t in range(0,seconds,window_seconds):
        duration=min(window_seconds,seconds-t)
        start=t*RATE; end=(t+duration)*RATE
        nblocks=(end-start)//FFT
        # 120 blocos independentes no tempo, uniformemente distribuidos pela janela
        inds=np.unique(np.linspace(0,nblocks-1,min(120,nblocks),dtype=np.int64))
        power=np.zeros(FFT,dtype=np.float64)
        for k in inds:
            pos=2*(start+int(k)*FFT)
            v=np.asarray(raw[pos:pos+2*FFT],dtype=np.float32)
            iq=(v[0::2]-127.5)+1j*(v[1::2]-127.5)
            z=np.fft.fftshift(np.fft.fft(iq*win))
            power+=np.abs(z)**2
        power/=len(inds)
        y=10*np.log10(np.maximum(power,1e-20))
        sm=np.convolve(np.pad(y,(17,17),mode='reflect'),np.ones(35)/35,mode='valid')
        baseline=np.convolve(np.pad(sm,(170,170),mode='reflect'),np.ones(341)/341,mode='valid')
        residual=sm-baseline
        # Estatisticas I/Q em 1 milhao de pares uniformemente espacados na janela
        ns=min(1_000_000,end-start)
        idx=np.linspace(start,end-1,ns,dtype=np.int64)
        i=np.asarray(raw[2*idx]); q=np.asarray(raw[2*idx+1])
        hi,mi=entropies(i);hq,mq=entropies(q)
        results.append(dict(start_s=t,end_s=t+duration,feature_db=float(np.median(residual[band])-np.median(residual[side])),
                            band_db=float(np.median(residual[band])),side_db=float(np.median(residual[side])),
                            shannon_i=hi,shannon_q=hq,marginal_min_i=mi,marginal_min_q=mq,
                            std_i=float(np.std(i)),std_q=float(np.std(q)),mean_i=float(np.mean(i)),mean_q=float(np.mean(q)),
                            fft_blocks=len(inds),iq_pairs_entropy_sampled=ns))
        print(f'  {path.stem}: {t}-{t+duration}s, excesso {results[-1]["feature_db"]:+.4f} dB',flush=True)
    return results

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dir',required=True)
    ap.add_argument('--window-seconds',type=int,default=10)
    a=ap.parse_args()
    if a.window_seconds<=0:ap.error('--window-seconds deve ser positivo')
    directory=Path(a.dir);meta_file=directory/'metadata.json'
    if not meta_file.exists():ap.error(f'Arquivo ausente: {meta_file}')
    meta=json.loads(meta_file.read_text());by={r['name']:r for r in meta}
    output=directory/'analysis_final';output.mkdir(exist_ok=True)
    rows=[]
    for name in NAMES:
        if name not in by or by[name].get('status')!='complete':ap.error(f'Captura {name} ausente/incompleta no metadata.json')
        rec=by[name];seconds=int(rec['duration_s']);path=directory/(name+'.cu8')
        if not path.exists():ap.error(f'Arquivo ausente: {path}')
        for result in process_file(path,seconds,a.window_seconds):rows.append(dict(capture=name,condition=rec['condition'],**result))
    with (output/'windows.csv').open('w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'description':'E7 exploratorio por janelas; entropias marginais nao equivalem a SP 800-90B',
             'frequency_hz':TARGET,'window_seconds':a.window_seconds,'captures':{}}
    for name in NAMES:
        subset=[r for r in rows if r['capture']==name]
        summary['captures'][name]={k:{'mean':float(np.mean([r[k] for r in subset])),
                                       'sd_between_windows':float(np.std([r[k] for r in subset],ddof=1)) if len(subset)>1 else None,
                                       'n_windows':len(subset)}
                                   for k in ['feature_db','shannon_i','shannon_q','marginal_min_i','marginal_min_q','std_i','std_q']}
    (output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    print('Concluido:',output/'windows.csv',output/'summary.json')
    print('IMPORTANTE: variacao entre janelas nao e teste de significancia de H I nem certificacao NIST.')
if __name__=='__main__':main()
