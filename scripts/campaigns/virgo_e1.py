#!/usr/bin/env python3
"""Virgo-RNG E1: captura controlada e analise ON/OFF/ON (CU8 RTL-SDR)."""
import argparse, datetime as dt, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np

STEPS=[('A1','50ohm'),('ON1','antenna'),('OFF','antenna'),('ON2','antenna'),('A2','50ohm')]

def stamp(): return dt.datetime.now(dt.timezone.utc).isoformat()
def save(path,obj): path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def capture(args):
    if not shutil.which('rtl_sdr'): sys.exit('ERRO: rtl_sdr nao encontrado. Instale rtl-sdr via Homebrew.')
    root=Path(args.out).expanduser().resolve()
    if root.exists() and any(root.iterdir()): sys.exit(f'ERRO: pasta nao vazia: {root}. Use novo --out.')
    root.mkdir(parents=True,exist_ok=True)
    n=int(args.rate*args.seconds)
    save(root/'campaign.json',{'protocol':'E1-A1-ON1-OFF-ON2-A2','created_utc':stamp(),'center_hz':args.freq,'rate_sps':args.rate,'gain_db':args.gain,'seconds':args.seconds,'samples_per_capture':n,'format':'CU8 interleaved I,Q','location':'Chapeco, SC (user reported)','notes':'Keep receiver settings fixed; use actual astronomical pointing coordinates and document times.'})
    for tag,condition in STEPS:
        print(f'\n=== {tag}: {condition} ===',flush=True)
        print('Conecte terminacao 50 ohms' if condition=='50ohm' else 'Conecte antena e ajuste apontamento.',flush=True)
        az=input('Azimute em graus (vazio se 50ohm): ').strip()
        el=input('Elevacao em graus (vazio se 50ohm): ').strip()
        target=input('Alvo/observacoes (ex. HI ON, referencia OFF): ').strip()
        input('Pressione ENTER quando estiver pronto para iniciar...')
        raw=root/f'{tag}.cu8'; meta=root/f'{tag}.json'
        cmd=['rtl_sdr','-d',str(args.device),'-f',str(args.freq),'-s',str(args.rate),'-g',str(args.gain),'-n',str(n),str(raw)]
        started=stamp(); t0=time.monotonic()
        with (root/f'{tag}.stderr.log').open('w') as err:
            rc=subprocess.run(cmd,stderr=err).returncode
        size=raw.stat().st_size if raw.exists() else 0
        record={'tag':tag,'condition':condition,'azimuth_deg':az,'elevation_deg':el,'target_notes':target,'start_utc':started,'end_utc':stamp(),'elapsed_s':time.monotonic()-t0,'command':cmd,'exit_code':rc,'actual_bytes':size,'expected_bytes':2*n,'complete':rc==0 and size==2*n}
        save(meta,record)
        print('OK' if record['complete'] else f'INCOMPLETA: veja {tag}.stderr.log',flush=True)
        if not record['complete']: sys.exit('Captura incompleta; pare e investigue antes de continuar.')
    print(f'\nCapturas concluidas em {root}. Execute: python virgo_e1.py analyze --dir "{root}"')

def spectrum(path,rate,fft_size,blocks):
    data=np.memmap(path,dtype=np.uint8,mode='r')
    total=len(data)//2
    if total < fft_size*blocks: raise ValueError(f'{path}: dados insuficientes')
    positions=np.linspace(0,total-fft_size,blocks,dtype=np.int64)
    window=np.hanning(fft_size); accum=np.zeros(fft_size,dtype=np.float64)
    hist_i=np.zeros(256,dtype=np.int64);hist_q=np.zeros(256,dtype=np.int64)
    for pos in positions:
        part=np.asarray(data[2*pos:2*(pos+fft_size)],dtype=np.float32)
        i=part[::2];q=part[1::2]
        hist_i+=np.bincount(i.astype(np.uint8),minlength=256)
        hist_q+=np.bincount(q.astype(np.uint8),minlength=256)
        z=(i-127.5)+1j*(q-127.5)
        z=z-np.mean(z)
        accum+=np.abs(np.fft.fftshift(np.fft.fft(z*window)))**2
    psd=accum/blocks/(window**2).sum()
    freq=np.fft.fftshift(np.fft.fftfreq(fft_size,1/rate))
    def entropy(hist):
        p=hist[hist>0]/hist.sum()
        return float(-np.sum(p*np.log2(p))),float(-np.log2(p.max()))
    return freq,psd,{'sampled_symbols':int(hist_i.sum()),'I_shannon_bits':entropy(hist_i)[0],'Q_shannon_bits':entropy(hist_q)[0],'I_marginal_min_bits':entropy(hist_i)[1],'Q_marginal_min_bits':entropy(hist_q)[1]}

def analyze(args):
    root=Path(args.dir).expanduser().resolve()
    campaign=json.loads((root/'campaign.json').read_text()); rate=campaign['rate_sps']; fc=campaign['center_hz']
    results={};freq=None
    for tag,_ in STEPS:
        p=root/f'{tag}.cu8'; meta=json.loads((root/f'{tag}.json').read_text())
        if not meta['complete']: sys.exit(f'{tag} incompleta')
        freq,psd,stats=spectrum(p,rate,args.fft,args.blocks)
        results[tag]={'psd':psd,'stats':stats,'metadata':meta}
        print(tag,stats,flush=True)
    # OFF comparison of ON1 and ON2, not absolute calibration. Exclude DC and edges.
    on=(results['ON1']['psd']+results['ON2']['psd'])/2
    off=results['OFF']['psd']; ratio=10*np.log10(np.maximum(on,1e-30)/np.maximum(off,1e-30))
    center_mask=(np.abs(freq)>args.dc_exclusion_hz)&(np.abs(freq)<rate*.42)
    peak_idx=np.argmax(np.where(center_mask,ratio,-np.inf))
    summary={'method':'Uncalibrated ON1/ON2 average vs OFF; power ratio, not confirmed HI detection','fft_size':args.fft,'blocks_per_capture':args.blocks,'frequency_center_hz':fc,'peak_offset_hz':float(freq[peak_idx]),'peak_frequency_hz':float(fc+freq[peak_idx]),'peak_on_off_db':float(ratio[peak_idx]),'caution':'No bandpass calibration; peak may be RFI, baseline drift or gain changes. Do not claim astronomical detection. Marginal entropy is not NIST min-entropy.','captures':{k:v['stats'] for k,v in results.items()}}
    out=root/'analysis';out.mkdir(exist_ok=True)
    save(out/'summary.json',summary)
    with (out/'spectra.csv').open('w') as f:
        f.write('frequency_hz,ON1_psd,OFF_psd,ON2_psd,A1_psd,A2_psd,ON_OFF_db\n')
        for j in range(len(freq)):
            f.write(f'{fc+freq[j]:.3f},{results["ON1"]["psd"][j]:.9g},{off[j]:.9g},{results["ON2"]["psd"][j]:.9g},{results["A1"]["psd"][j]:.9g},{results["A2"]["psd"][j]:.9g},{ratio[j]:.6f}\n')
    print('\nRESUMO:',json.dumps(summary,indent=2,ensure_ascii=False));print('Arquivos:',out)

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    c=sub.add_parser('capture');c.add_argument('--out',required=True);c.add_argument('--freq',type=int,default=1420405752);c.add_argument('--rate',type=int,default=2400000);c.add_argument('--gain',type=float,default=30);c.add_argument('--seconds',type=int,default=180);c.add_argument('--device',type=int,default=0)
    a=sub.add_parser('analyze');a.add_argument('--dir',required=True);a.add_argument('--fft',type=int,default=4096);a.add_argument('--blocks',type=int,default=3000);a.add_argument('--dc-exclusion-hz',type=float,default=10000)
    args=p.parse_args()
    if args.action=='capture': capture(args)
    else: analyze(args)
if __name__=='__main__':main()
