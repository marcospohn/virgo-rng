#!/usr/bin/env python3
"""E7: campanha final A1 ON1 OFF1 ON2 OFF2 ON3 A2 e analise espectral.
Requer rtl_sdr no PATH (captura), numpy (analise). Arquivos CU8 sao preservados.
"""
import argparse, csv, json, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

RATE=2_400_000
CENTER=1_420_405_752
GAIN=30
FFT=8192
STEPS=[('A1','LOAD',60),('ON1','ON',180),('OFF1','OFF',180),('ON2','ON',180),('OFF2','OFF',180),('ON3','ON',180),('A2','LOAD',60)]
TARGET=1_420_392_000
TARGET_HALF_WIDTH=20_000

def now(): return datetime.now(timezone.utc).isoformat()

def save_meta(path,meta):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(meta,indent=2,ensure_ascii=False));tmp.replace(path)

def capture(directory,seconds_on,seconds_load):
    if shutil.which('rtl_sdr') is None:
        sys.exit('ERRO: rtl_sdr nao encontrado no PATH.')
    directory.mkdir(parents=True,exist_ok=True)
    mf=directory/'metadata.json'
    try:
        meta=json.loads(mf.read_text()) if mf.exists() else []
        if not isinstance(meta,list): raise ValueError('metadata.json nao e uma lista')
    except (ValueError,OSError) as e:
        sys.exit(f'ERRO ao ler metadata.json: {e}. Nao alterei arquivos.')
    for name,condition,_ in STEPS:
        seconds=seconds_load if condition=='LOAD' else seconds_on
        expected=2*RATE*seconds
        path=directory/f'{name}.cu8'
        rec=next((r for r in meta if r.get('name')==name and r.get('status')=='complete'),None)
        if rec is not None:
            if path.is_file() and path.stat().st_size==int(rec.get('bytes',-1))==expected:
                print(f'{name}: concluida e verificada ({expected:,} bytes); pulando.',flush=True)
                continue
            sys.exit(f'ERRO: {name} consta como completa, mas o arquivo esta ausente ou com tamanho incorreto. '
                     'Nao vou sobrescrever; confira metadata.json e o CU8.')
        if path.exists():
            if path.stat().st_size==expected:
                print(f'ATENCAO: {name}.cu8 tem tamanho completo, mas nao ha registro completo no metadata.json.')
                print('Para evitar considerar dados possivelmente corrompidos como validos, nao vou usar esse arquivo.')
                print('Renomeie-o manualmente para inspecao e execute novamente.')
                sys.exit(2)
            backup=directory/f'{name}.incompleto_{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.cu8'
            idx=1
            while backup.exists():
                backup=directory/f'{name}.incompleto_{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}_{idx}.cu8'
                idx+=1
            path.rename(backup)
            print(f'{name}: arquivo parcial preservado em {backup.name}',flush=True)
        print(f'\\n{name} ({condition}) | {seconds}s | {CENTER/1e6:.6f} MHz | ganho {GAIN} dB',flush=True)
        if condition=='LOAD':
            print('Desligue Bias-T antes de trocar a conexao; conecte carga 50 ohms na entrada SAWbird; religue Bias-T.')
            az=el=None
        else:
            print('ON: mesmo alvo celeste em Carina. OFF: referencia definida e registrada.')
            try:
                az=float(input('Azimute real (graus): ').replace(',','.'))
                el=float(input('Elevacao real (graus): ').replace(',','.'))
                if not (0<=az<360 and 0<=el<=90): raise ValueError
            except ValueError:
                sys.exit('ERRO: azimute ou elevacao invalidos.')
        notes=input('Observacoes opcionais (Enter para nenhuma): ').strip()
        input('Confirme conexao, apontamento e alimentacao; Enter para iniciar: ')
        cmd=['rtl_sdr','-f',str(CENTER),'-s',str(RATE),'-g',str(GAIN),'-n',str(RATE*seconds),str(path)]
        attempt=0
        while True:
            attempt+=1
            print(f'{name}: tentativa {attempt}.',flush=True)
            start=now()
            try:
                result=subprocess.run(cmd,check=False)
                error=None if result.returncode==0 else f'rtl_sdr retornou codigo {result.returncode}'
            except OSError as e:
                error=str(e)
            end=now()
            actual=path.stat().st_size if path.exists() else 0
            if error is None and actual==expected:
                rec=dict(name=name,condition=condition,azimuth_deg=az,elevation_deg=el,notes=notes,
                         center_hz=CENTER,sample_rate_hz=RATE,gain_db_requested=GAIN,
                         agc_requested=False,duration_s=seconds,start_utc=start,end_utc=end,
                         bytes=actual,status='complete',filename=path.name,format='cu8_interleaved_iq')
                meta=[r for r in meta if r.get('name')!=name]+[rec]
                save_meta(mf,meta)
                print(f'{name}: OK ({actual:,} bytes). Progresso salvo.',flush=True)
                break
            print(f'FALHA em {name}: {error or "tamanho incorreto"}; '
                  f'obtidos {actual:,} de {expected:,} bytes.',flush=True)
            if path.exists():
                backup=directory/f'{name}.falha_{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}_{attempt}.cu8'
                path.rename(backup)
                print(f'Arquivo da tentativa preservado: {backup.name}',flush=True)
            choice=input('[R]etentar esta captura, [S]air para retomar depois? [R/s]: ').strip().lower()
            if choice in ('s','sair','q','quit'):
                print(f'Interrompido. Para retomar, repita o mesmo comando --dir {directory}',flush=True)
                return
            input('Verifique SDR, cabo USB, alimentacao e apontamento; Enter para tentar novamente: ')
    print('\\nE7 concluido. Execute: python virgo_e7.py analyze --dir '+str(directory),flush=True)

def spectrum(path,fft=FFT,max_blocks=3000):
    raw=np.memmap(path,dtype=np.uint8,mode='r')
    blocks=raw.size//(2*fft)
    if blocks<1: raise ValueError('Arquivo curto: '+str(path))
    indices=np.unique(np.linspace(0,blocks-1,min(blocks,max_blocks),dtype=np.int64))
    win=np.hanning(fft).astype(np.float32); acc=np.zeros(fft,dtype=np.float64)
    for k in indices:
        a=np.asarray(raw[int(k)*2*fft:(int(k)+1)*2*fft],dtype=np.float32)
        iq=(a[::2]-127.5)+1j*(a[1::2]-127.5)
        ft=np.fft.fftshift(np.fft.fft(iq*win))
        acc+=np.abs(ft)**2
    return acc/len(indices),len(indices)

def moving_mean(x,n):
    n=max(1,int(n)|1)
    return np.convolve(np.pad(x,(n//2,n//2),mode='reflect'),np.ones(n)/n,mode='valid')

def analyze(directory):
    mf=directory/'metadata.json'
    if not mf.exists():sys.exit('metadata.json nao encontrado')
    records=json.loads(mf.read_text());byname={r['name']:r for r in records}
    names=[s[0] for s in STEPS]
    if any(n not in byname or byname[n].get('status')!='complete' for n in names):sys.exit('Faltam capturas completas para analise.')
    out=directory/'analysis';out.mkdir(exist_ok=True)
    freq=CENTER+np.fft.fftshift(np.fft.fftfreq(FFT,d=1/RATE))
    spectra={};nblocks={}
    for name in names:
        print('Processando',name,flush=True)
        spectra[name],nblocks[name]=spectrum(directory/(name+'.cu8'))
    with (out/'individual_spectra.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['frequency_hz']+names)
        for i,fr in enumerate(freq):w.writerow([f'{fr:.5f}']+[f'{spectra[n][i]:.9g}' for n in names])
    # Comparacoes ON/OFF: OFF1 serve para ON1 e ON2; OFF2 para ON2 e ON3.
    pairs=[('ON1','OFF1'),('ON2','OFF1'),('ON2','OFF2'),('ON3','OFF2')]
    band=(freq>=TARGET-TARGET_HALF_WIDTH)&(freq<=TARGET+TARGET_HALF_WIDTH)
    # Controles laterais predefinidos; mantidos fora da janela candidata.
    side=((freq>=TARGET-80_000)&(freq<=TARGET-40_000))|((freq>=TARGET+40_000)&(freq<=TARGET+80_000))
    valid=np.abs(freq-CENTER)<900_000
    summary=dict(protocol='E7 Carina, 7 captures, preselected 1420.392 MHz +/-20 kHz',
                 center_hz=CENTER,sample_rate_hz=RATE,fft_size=FFT,resolution_hz=RATE/FFT,
                 target_hz=TARGET,target_half_width_hz=TARGET_HALF_WIDTH,
                 caution='Nao e calibracao astronomica. Comparacoes de espectros nao provam H I; OFF pode conter HI e RFI.',
                 blocks_used=nblocks,pairs=[])
    with (out/'contrasts.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['pair','frequency_hz','raw_ratio_db','smoothed_10khz_db','residual_100khz_db'])
        for on,off in pairs:
            ratio=10*np.log10(np.maximum(spectra[on],1e-30)/np.maximum(spectra[off],1e-30))
            sm=moving_mean(ratio,35) # ~10.25 kHz
            baseline=moving_mean(sm,341) # ~100 kHz
            residual=sm-baseline
            rec=dict(pair=f'{on}_{off}',raw_band_median_db=float(np.median(ratio[band])),
                     residual_band_median_db=float(np.median(residual[band])),
                     residual_band_max_db=float(np.max(residual[band])),
                     residual_sideband_median_db=float(np.median(residual[side])),
                     band_minus_sideband_db=float(np.median(residual[band])-np.median(residual[side])),
                     broad_band_median_db=float(np.median(ratio[valid])))
            summary['pairs'].append(rec)
            for i,fr in enumerate(freq):w.writerow([rec['pair'],f'{fr:.5f}',f'{ratio[i]:.7f}',f'{sm[i]:.7f}',f'{residual[i]:.7f}'])
    save_meta(out/'summary.json',summary)
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    print('Arquivos:',out/'summary.json',out/'individual_spectra.csv',out/'contrasts.csv')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['capture','analyze'])
    p.add_argument('--dir',default='results/E7_carina')
    p.add_argument('--seconds-on',type=int,default=180)
    p.add_argument('--seconds-load',type=int,default=60)
    a=p.parse_args()
    if a.seconds_on<1 or a.seconds_load<1:p.error('Duracoes devem ser positivas.')
    if a.action=='capture':capture(Path(a.dir),a.seconds_on,a.seconds_load)
    else:analyze(Path(a.dir))
