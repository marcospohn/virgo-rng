#!/usr/bin/env python3
"""E6: teste de reproducibilidade espectral com duas sintonias e ON/OFF intercalados.
Requer rtl_sdr no PATH e numpy. Nao declara deteccao astronomica.
"""
import argparse, csv, json, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

RATE=2400000
GAIN=30
FFT=8192
TARGET=1420331000
# Frequencias suficientemente separadas para mudar a posicao do alvo na banda
STEPS=[('ON1',1420105752,'ON'),('OFF1',1420105752,'OFF'),('ON2',1420705752,'ON'),('OFF2',1420705752,'OFF'),('ON3',1420105752,'ON'),('OFF3',1420105752,'OFF')]

def utc(): return datetime.now(timezone.utc).isoformat()
def acquire(directory,seconds):
    if not shutil.which('rtl_sdr'): sys.exit('rtl_sdr nao encontrado no PATH')
    directory.mkdir(parents=True,exist_ok=True)
    meta=[]
    for name,fc,pointing in STEPS:
        path=directory/(name+'.cu8')
        if path.exists(): sys.exit(f'Arquivo ja existe: {path}. Use outro --dir.')
        print(f'\n{name}: {pointing}; centro {fc/1e6:.6f} MHz; {seconds} s',flush=True)
        print('ON: centro galactico via Stellarium. OFF: direcao livre de obstaculos, sugerida 300/60, registre angulos.')
        try:
            az=float(input('Azimute real (graus): ')); el=float(input('Elevacao real (graus): '))
            if not (0<=az<360 and 0<=el<=90): raise ValueError()
        except ValueError: sys.exit('Coordenadas invalidas')
        input('Pressione Enter quando a antena estiver apontada: ')
        begin=utc(); n=RATE*seconds
        command=['rtl_sdr','-f',str(fc),'-s',str(RATE),'-g',str(GAIN),'-n',str(n),str(path)]
        subprocess.run(command,check=True)
        end=utc()
        if path.stat().st_size!=2*n: sys.exit(f'Tamanho inesperado de {path}')
        meta.append(dict(name=name,pointing=pointing,azimuth_deg=az,elevation_deg=el,center_hz=fc,rate_hz=RATE,gain_db=GAIN,seconds=seconds,start_utc=begin,end_utc=end,bytes=path.stat().st_size))
        (directory/'metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False))
    print('Captura completa. Execute analyze.')

def power_spectrum(path):
    raw=np.memmap(path,dtype=np.uint8,mode='r')
    nblock=raw.size//(FFT*2)
    if nblock<1: raise ValueError(f'Arquivo muito curto: {path}')
    ids=np.unique(np.linspace(0,nblock-1,min(nblock,2500),dtype=np.int64))
    win=np.hanning(FFT).astype(np.float32)
    acc=np.zeros(FFT)
    for k in ids:
        v=np.asarray(raw[int(k)*FFT*2:(int(k)+1)*FFT*2],dtype=np.float32)
        iq=(v[::2]-127.5)+1j*(v[1::2]-127.5)
        ft=np.fft.fftshift(np.fft.fft(iq*win))
        acc+=np.abs(ft)**2
    return acc/len(ids)

def smooth(y,window):
    if window%2==0: window+=1
    pad=window//2
    return np.convolve(np.pad(y,(pad,pad),mode='reflect'),np.ones(window)/window,mode='valid')

def analyze(directory):
    meta_file=directory/'metadata.json'
    if not meta_file.exists(): sys.exit('metadata.json ausente')
    meta=json.loads(meta_file.read_text())
    if len(meta)!=6: sys.exit('Sao necessarias seis capturas completas')
    specs={}; axes={}
    for rec in meta:
        name=rec['name']; print('Processando',name,flush=True)
        specs[name]=power_spectrum(directory/(name+'.cu8'))
        axes[name]=rec['center_hz']+np.fft.fftshift(np.fft.fftfreq(FFT,1/RATE))
    # Cada ON/OFF no mesmo centro; razao elimina parte da resposta da cadeia, nao a calibra completamente.
    pairs=[('ON1','OFF1'),('ON2','OFF2'),('ON3','OFF3')]
    out=directory/'analysis';out.mkdir(exist_ok=True)
    records=[]; summary={'target_hz':TARGET,'resolution_hz':RATE/FFT,'pairs':[],'caution':'Contraste sem calibracao absoluta; diferentes elevacoes e RFI podem contaminar o resultado.'}
    for on,off in pairs:
        freq=axes[on]; ratio=10*np.log10(np.maximum(specs[on],1e-20)/np.maximum(specs[off],1e-20))
        # Suavizacao 31 canais (~9.1 kHz) para reduzir picos estreitos; nao e mascaramento formal de RFI.
        sm=smooth(ratio,31)
        # Corrige apenas um nivel constante pela mediana da banda interior; nao ajusta polinomio que poderia remover H I.
        interior=(abs(freq-meta[[x['name'] for x in meta].index(on)]['center_hz'])<900000)
        norm=sm-np.median(sm[interior])
        band=(freq>=1420313000)&(freq<=1420350000)
        # Intervalo 1420.313–1420.350 MHz foi selecionado exploratoriamente no E5, nao e teste independente.
        result={'on':on,'off':off,'center_hz':int(meta[[x['name'] for x in meta].index(on)]['center_hz']), 'band_median_db':float(np.median(norm[band])),'band_peak_db':float(np.max(norm[band])),'band_channels':int(np.count_nonzero(band))}
        summary['pairs'].append(result)
        for f,r,s in zip(freq,ratio,norm): records.append((on+'_'+off,round(f,3),round(float(r),7),round(float(s),7)))
    with (out/'spectra_contrasts.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['pair','frequency_hz','raw_on_off_db','smoothed_median_centered_db']);w.writerows(records)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    print('Arquivos:',out/'summary.json',out/'spectra_contrasts.csv')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['capture','analyze'])
    p.add_argument('--dir',default='results/E6_freq_switch')
    p.add_argument('--seconds',type=int,default=90)
    a=p.parse_args()
    if a.seconds<=0:p.error('--seconds deve ser positivo')
    if a.action=='capture':acquire(Path(a.dir),a.seconds)
    else:analyze(Path(a.dir))
