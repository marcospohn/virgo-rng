#!/usr/bin/env python3
"""E4: ON1/OFF/ON2, teste de dependencia direcional."""
import argparse, csv, json, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

RATE=2_400_000
FREQ=1_420_405_752
GAIN=30
TARGET=1_419_988_565
FFT=4096

def stamp(): return datetime.now(timezone.utc).isoformat()

def capture(out, seconds):
    if not shutil.which('rtl_sdr'):
        sys.exit('ERRO: rtl_sdr nao encontrado. Instale-o e confirme no PATH.')
    out.mkdir(parents=True, exist_ok=True)
    metadata=[]
    for name, connection in [('ON1','Centro galactico'),('OFF','Referencia fora do plano galactico'),('ON2','Centro galactico')]:
        file=out/f'{name}.cu8'
        if file.exists():
            sys.exit(f'ERRO: {file} ja existe; use outro diretorio para nao sobrescrever.')
        print(f'\n{name}: {connection}. Mantenha a antena conectada e o Bias-T inalterado.', flush=True)
        az=input('Azimute real (graus, conforme Stellarium): ').strip()
        el=input('Elevacao real (graus, conforme Stellarium): ').strip()
        try:
            az=float(az);el=float(el)
            if not (0<=az<360 and 0<=el<=90): raise ValueError()
        except ValueError: sys.exit('ERRO: apontamento invalido.')
        input('Confirme antena apontada e pressione Enter: ')
        begin=stamp()
        samples=RATE*seconds
        command=['rtl_sdr','-f',str(FREQ),'-s',str(RATE),'-g',str(GAIN),'-n',str(samples),str(file)]
        subprocess.run(command,check=True)
        end=stamp()
        actual=file.stat().st_size
        if actual!=samples*2:
            sys.exit(f'ERRO: {file}: {actual} bytes; esperados {samples*2}.')
        metadata.append(dict(capture=name,connection=connection,azimuth_deg=az,elevation_deg=el,start_utc=begin,end_utc=end,center_hz=FREQ,sample_rate=RATE,gain_db=GAIN,seconds=seconds,bytes=actual))
        (out/'metadata.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False))
    print('\nCapturas completas. Execute: python virgo_e4.py analyze --dir',out)

def spectrum(file):
    raw=np.memmap(file,dtype=np.uint8,mode='r')
    n_complex=raw.size//2
    total_blocks=n_complex//FFT
    if total_blocks<1: raise ValueError(f'Arquivo muito pequeno: {file}')
    # Seleciona blocos uniformemente ao longo de toda a aquisicao.
    indexes=np.unique(np.linspace(0,total_blocks-1,min(total_blocks,4096),dtype=np.int64))
    window=np.hanning(FFT).astype(np.float32)
    acc=np.zeros(FFT,dtype=np.float64)
    for idx in indexes:
        start=int(idx)*FFT*2
        b=np.asarray(raw[start:start+FFT*2],dtype=np.float32)
        iq=(b[::2]-127.5)+1j*(b[1::2]-127.5)
        transformed=np.fft.fftshift(np.fft.fft(iq*window))
        acc+=np.abs(transformed)**2
    return acc/len(indexes),len(indexes)

def analyze(out):
    names=['ON1','OFF','ON2']
    missing=[name for name in names if not (out/f'{name}.cu8').exists()]
    if missing: sys.exit('Faltam arquivos: '+', '.join(missing))
    freqs=FREQ+np.fft.fftshift(np.fft.fftfreq(FFT,1/RATE))
    spec={}; blocks={}
    for name in names:
        print('Analisando',name,flush=True)
        spec[name],blocks[name]=spectrum(out/f'{name}.cu8')
    out_analysis=out/'analysis';out_analysis.mkdir(exist_ok=True)
    with (out_analysis/'spectra.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['frequency_hz','ON1_power','OFF_power','ON2_power'])
        w.writerows(zip(freqs,spec['ON1'],spec['OFF'],spec['ON2']))
    idx=int(np.argmin(abs(freqs-TARGET)))
    # Exclui +/- 5 bins e usa banda lateral de 10 a 60 bins como referencia local.
    offsets=np.arange(-60,61)
    neighbors=idx+offsets[(np.abs(offsets)>=10)]
    neighbors=neighbors[(neighbors>=0)&(neighbors<FFT)]
    report={'target_hz':TARGET,'nearest_bin_hz':float(freqs[idx]),'resolution_hz':RATE/FFT,'captures':{}}
    for name in names:
        peak=float(spec[name][idx]);baseline=float(np.median(spec[name][neighbors]))
        report['captures'][name]={'peak_power':peak,'local_baseline_power':baseline,'excess_db':float(10*np.log10(peak/baseline)),'blocks_used':blocks[name]}
    report['on_vs_off_excess_db']=float(np.mean([report['captures'][x]['excess_db'] for x in ('ON1','ON2')])-report['captures']['OFF']['excess_db'])
    report['on_repeat_difference_db']=float(report['captures']['ON2']['excess_db']-report['captures']['ON1']['excess_db'])
    (out_analysis/'summary.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    print('\nEnvie somente analysis/summary.json e analysis/spectra.csv (nao precisa enviar os CU8).')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['capture','analyze'])
    p.add_argument('--dir',default='results/E4_direcional')
    p.add_argument('--seconds',type=int,default=60)
    args=p.parse_args()
    if args.seconds<=0: p.error('--seconds deve ser positivo')
    if args.action=='capture': capture(Path(args.dir),args.seconds)
    else: analyze(Path(args.dir))
