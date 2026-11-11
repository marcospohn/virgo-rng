#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Virgo-RNG: reprocessar os CU8 ja coletados de E4 (duas campanhas) e E5.

Executar no diretorio principal do projeto Virgo-RNG 2.0:
    python virgo_e4_e5_reprocessar_integral.py \
        --dir-first results/E4_direcional \
        --dir-repeat results/E4_repeticao

Sem RTL-SDR conectado. Nunca captura nem altera CU8 ou metadata.json.
E5 e uma reanalise da SEGUNDA campanha E4; NAO e coleta independente.
Testa dois candidatos distintos:
  - estreito: 1419.988565 MHz (E4; controles direcionais negativos anteriormente)
  - largo:    1420.330752 MHz (E5; escolhido de forma exploratoria)

Resultados sao medidas relativas sem calibracao astronomica; nao provam H I.
Requer Python >= 3.9, numpy; scipy e matplotlib recomendados.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import os
import sys
import zipfile
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

VERSION = '1.0.0'
RATE = 2_400_000
CENTER = 1_420_405_752
NARROW = 1_419_988_565
BROAD = 1_420_330_752
NAMES = ('ON1', 'OFF', 'ON2')
EPS = 1e-28


def dump_json(path: Path, obj) -> None:
    tmp=path.with_name('.'+path.name+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    os.replace(tmp,path)


def csv_rows(path: Path, cols, rows) -> None:
    tmp=path.with_name('.'+path.name+'.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(cols)
        for r in rows: w.writerow(r)
    os.replace(tmp,path)


def metadados(folder: Path, rate: int, center: int):
    mpath=folder/'metadata.json'
    if not mpath.is_file():
        raise ValueError(f'Metadados ausentes: {mpath}')
    records=json.loads(mpath.read_text(encoding='utf-8'))
    if not isinstance(records,list): raise ValueError(f'{mpath}: esperava lista')
    by={}
    for r in records:
        if not isinstance(r,dict): raise ValueError(f'{mpath}: registro nao e objeto')
        name=r.get('capture',r.get('name'))
        if name not in NAMES: raise ValueError(f'{mpath}: captura desconhecida {name}')
        if name in by: raise ValueError(f'{mpath}: captura duplicada {name}')
        by[name]=r
    if set(by)!=set(NAMES): raise ValueError(f'{mpath}: requer {NAMES}; presentes: {list(by)}')
    for name,r in by.items():
        if int(r.get('center_hz',-1)) != center:
            raise ValueError(f'{folder}/{name}: centro difere de {center} Hz')
        if int(r.get('sample_rate',r.get('rate_hz',r.get('sample_rate_hz',-1)))) != rate:
            raise ValueError(f'{folder}/{name}: taxa de amostragem incorreta')
        fp=folder/f'{name}.cu8'
        if not fp.is_file(): raise ValueError(f'Arquivo ausente: {fp}')
        size=fp.stat().st_size
        if size != int(r.get('bytes',-1)) or size%2:
            raise ValueError(f'{fp}: tamanho de {size} bytes nao coincide com os metadados ({r.get("bytes")})')
        if size < 16384 * 2: raise ValueError(f'{fp}: muito pequeno')
        secs=r.get('seconds',r.get('duration_s'))
        if secs is not None and abs(size/(2*rate)-float(secs)) > .02:
            raise ValueError(f'{fp}: duracao diverge da quantidade de amostras')
    return by


def odd_bins(khz, bin_hz):
    n=max(1,int(round(khz*1000/bin_hz)))
    return n if n%2 else n+1


def mov(x,n):
    if n==1: return np.array(x,copy=True)
    k=n//2
    return np.convolve(np.pad(x,(k,k),mode='reflect'),np.ones(n,dtype=float)/n,mode='valid')


def interpolate_center(freq, y, center, mask_khz):
    if mask_khz<=0: return np.asarray(y).copy()
    good=np.abs(freq-center)>mask_khz*1000
    if np.count_nonzero(good)<4: raise ValueError('Mascara central exagerada')
    return np.interp(freq,freq[good],y[good])


def baseline_residual(freq, ratio, center, mask_khz, smooth_bins, base_bins):
    cleaned=interpolate_center(freq,ratio,center,mask_khz)
    sm=mov(cleaned,smooth_bins)
    return sm-mov(sm,base_bins)


def broad_measure(freq, raw, residual, center, mask_khz, target=BROAD,half_khz=20):
    offset=(freq-target)/1000.0
    main=np.abs(offset)<=half_khz
    sides=(np.abs(offset)>=2*half_khz)&(np.abs(offset)<=4*half_khz)
    if mask_khz:
        keep=np.abs(freq-center)>mask_khz*1000
        main &= keep; sides &= keep
    if np.count_nonzero(main)<5 or np.count_nonzero(sides)<10:
        raise ValueError('Alvo ou faixas laterais sem canais suficientes')
    coef=np.polyfit(offset[sides],raw[sides],1)
    peak_idx=np.flatnonzero(main)[np.argmax(residual[main])]
    return {
        'feature_db':float(np.median(residual[main])-np.median(residual[sides])),
        'linear_sideband_fit_db':float(np.median(raw[main]-np.polyval(coef,offset[main]))),
        'peak_hz_exploratory':float(freq[peak_idx]),
        'peak_residual_db':float(residual[peak_idx]),
        'n_band_bins':int(main.sum()),'n_side_bins':int(sides.sum()),
    }


def narrow_measure(freq, power, target=NARROW):
    """Per-capture: narrow peak within +/- 1.5 kHz and local baseline 10-35 kHz away."""
    d=np.abs(freq-target)
    main=d<=1500
    sides=(d>=10_000)&(d<=35_000)
    if main.sum()<2 or sides.sum()<8:
        raise ValueError('Numero insuficiente de canais na janela estreita')
    ix=np.flatnonzero(main)[np.argmax(power[main])]
    return {'peak_frequency_hz':float(freq[ix]),
            'peak_vs_local_baseline_db':float(10*np.log10(max(float(power[ix]),EPS)/max(float(np.median(power[sides])),EPS))),
            'peak_power_uncalibrated':float(power[ix])}


def process(path:Path, rate, fft, window_s, batch):
    raw=np.memmap(path,mode='r',dtype=np.uint8)
    samples=raw.size//2
    nblocks=samples//fft
    if nblocks<4:raise ValueError(f'{path}: capturas com menos de 4 blocos FFT')
    bw=max(1,int(round(window_s*rate/fft)))
    count_windows=(nblocks+bw-1)//bw
    win=np.hanning(fft).astype(np.float32)
    winfft=np.fft.fft(win)
    acc0=np.zeros(fft,dtype=np.float64)
    acc1=np.zeros(fft,dtype=np.float64)
    w0=[];w1=[];wininfo=[];sum_means=0j
    for iw in range(count_windows):
        a=iw*bw;b=min(nblocks,(iw+1)*bw)
        s0=np.zeros(fft,np.float64);s1=np.zeros(fft,np.float64)
        for block in range(a,b,batch):
            nb=min(batch,b-block)
            pos=block*fft*2
            u=np.asarray(raw[pos:pos+nb*fft*2],dtype=np.float32).reshape(nb,fft,2)
            iq=(u[:,:,0]-127.5)+1j*(u[:,:,1]-127.5)
            means=np.mean(iq,axis=1)
            sum_means+=complex(np.sum(means))
            ft=np.fft.fft(iq*win,axis=1)
            s0+=np.sum(np.abs(ft)**2,axis=0)
            ft-=means[:,None]*winfft[None,:]
            s1+=np.sum(np.abs(ft)**2,axis=0)
        n=b-a
        acc0+=s0;acc1+=s1
        w0.append(np.fft.fftshift(s0/n));w1.append(np.fft.fftshift(s1/n))
        wininfo.append([a*fft/rate,b*fft/rate,n])
        print(f'  {path.name}: janela {iw+1}/{count_windows}',flush=True)
    del raw
    return {'p_raw':np.fft.fftshift(acc0/nblocks),
            'p_dc':np.fft.fftshift(acc1/nblocks),
            'w_raw':np.stack(w0), 'w_dc':np.stack(w1),
            'w_info':np.asarray(wininfo,dtype=float),
            'n_fft':np.int64(nblocks),'n_samples':np.int64(samples),
            'discarded_samples':np.int64(samples-nblocks*fft),
            'dc_mean_i':np.float64((sum_means/nblocks).real),
            'dc_mean_q':np.float64((sum_means/nblocks).imag)}


def load_capture(path, rec, cache_dir, campaign, name, args):
    st=path.stat()
    # Filename and mtime included: protects against accidentally reusing a different CU8.
    fingerprint={'version':VERSION,'path':str(path.resolve()),'bytes':st.st_size,
                 'mtime_ns':st.st_mtime_ns,'rate':args.rate,'fft':args.fft,
                 'window_s':args.window_seconds,'center':int(rec['center_hz'])}
    cache_dir.mkdir(parents=True,exist_ok=True)
    cache=cache_dir/f'{campaign}_{name}_fft{args.fft}.npz'
    if cache.is_file() and not args.force:
        try:
            with np.load(cache,allow_pickle=False) as z:
                if json.loads(str(z['fingerprint'].item()))==fingerprint:
                    print(f'{campaign} {name}: cache valido, pulando leitura CU8',flush=True)
                    return {k:z[k].copy() for k in z.files if k!='fingerprint'}
        except (ValueError,KeyError,OSError,json.JSONDecodeError):pass
    print(f'{campaign} {name}: lendo CU8 integral ({st.st_size/1e6:.1f} MB)',flush=True)
    result=process(path,args.rate,args.fft,args.window_seconds,args.batch_blocks)
    tmp=cache_dir/f'.{campaign}_{name}_fft{args.fft}.tmp.npz'
    with tmp.open('wb') as f:np.savez_compressed(f,fingerprint=json.dumps(fingerprint),**result)
    os.replace(tmp,cache)
    return result


def e5_legacy_like(ratio, bin_hz):
    """E5: median width ~24 kHz; Gaussian sigma ~129/14.65 kHz.

    The original E5 processing used 4096-point PSD from sampled blocks, not all
    CU8 blocks. Recompute at actual FFT resolution and preserve PHYSICAL widths.
    """
    from scipy.ndimage import median_filter, gaussian_filter1d
    med_bins=odd_bins(41*(RATE/4096)/1000,bin_hz)
    sigma_base=220*(RATE/4096)/bin_hz
    sigma_smooth=25*(RATE/4096)/bin_hz
    median=median_filter(ratio,size=med_bins,mode='nearest')
    baseline=gaussian_filter1d(median,sigma=sigma_base)
    residual=gaussian_filter1d(np.clip(ratio-baseline,-3,3),sigma=sigma_smooth)
    return baseline,residual,{'median_bins':int(med_bins), 'gaussian_baseline_sigma_bins':float(sigma_base),
                               'gaussian_residual_sigma_bins':float(sigma_smooth)}


def optional_graphs(out,pairs,windows):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('matplotlib ausente: CSV/JSON gerados sem graficos.',flush=True)
        return
    # The broad region and narrow feature are far apart: separate panels.
    fig,axes=plt.subplots(2,2,figsize=(12,7.5),constrained_layout=True)
    for p in pairs:
        if p['method']!='after_dc' or p['baseline_khz']!=100 or p['mask_khz']!=5:
            continue
        fq=p['freq'];y=p['res'];label=p['campaign']+' '+p['pair']
        idx=np.abs(fq-BROAD)<=140_000
        axes[0,0].plot(fq[idx]/1e6,y[idx],label=label,lw=1)
        axes[1,0].plot(fq[idx]/1e6,p['ratio'][idx],label=label,lw=1)
        idx2=np.abs(fq-NARROW)<=35_000
        axes[0,1].plot(fq[idx2]/1e6,y[idx2],label=label,lw=1)
        axes[1,1].plot(fq[idx2]/1e6,p['ratio'][idx2],label=label,lw=1)
    for ax in axes.flat:
        ax.grid(alpha=.2)
        ax.tick_params(axis='x',labelsize=8)
        ax.legend(fontsize=7)
    axes[0,0].set(title='E5 exploratory broad candidate — residual',ylabel='ON/OFF residual (dB)')
    axes[1,0].set(title='Broad candidate — raw ratio',xlabel='Absolute RF (MHz)',ylabel='ON/OFF raw ratio (dB)')
    axes[0,1].set(title='E4 narrow feature — residual',ylabel='Residual (dB)')
    axes[1,1].set(title='Narrow feature — raw ratio',xlabel='Absolute RF (MHz)',ylabel='ON/OFF raw ratio (dB)')
    for ax,target,half in [(axes[0,0],BROAD,20_000),(axes[1,0],BROAD,20_000)]:
        ax.axvspan((target-half)/1e6,(target+half)/1e6,alpha=.12,color='grey')
    fig.savefig(out/'e4_e5_spectra.png',dpi=170);plt.close(fig)

    fig,ax=plt.subplots(figsize=(10,4.2),constrained_layout=True)
    mapping={'first ON1/OFF':0,'first ON2/OFF':1,
             'repeat ON1/OFF':2,'repeat ON2/OFF':3}
    for r in windows:
        if r['method']!='after_dc' or r['band']!='broad' or r['baseline_khz']!=100 or r['mask_khz']!=5:
            continue
        k=mapping[r['campaign']+' '+r['pair']]
        ax.scatter(k+.1+(r['window_index']+.5)*.8/6,r['feature_db'],s=18)
    ax.set_xticks(np.arange(4)+.5,list(mapping));ax.axhline(0,color='gray',lw=.9)
    ax.set(ylabel='Band-minus-sideband (dB)',title='E4 two campaigns; E5 candidate, non-simultaneous windows')
    ax.grid(axis='y',alpha=.3)
    fig.savefig(out/'e4_e5_temporal.png',dpi=170);plt.close(fig)


def zip_results(out):
    dest=out.parent/'E4_E5_reprocessamento_resultados.zip'
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.iterdir()):
            if f.is_file() and f.suffix in ('.csv','.json','.png','.txt','.md'):
                z.write(f,arcname=f.name)
    return dest


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--dir-first',type=Path,default=Path('results/E4_direcional'))
    p.add_argument('--dir-repeat',type=Path,default=Path('results/E4_repeticao'))
    p.add_argument('--only',choices=['first','repeat','both'],default='both')
    p.add_argument('--output',type=Path,default=Path('results/E4_E5_reprocessing'))
    p.add_argument('--fft',type=int,default=8192)
    p.add_argument('--rate',type=int,default=RATE)
    p.add_argument('--center-hz',type=int,default=CENTER)
    p.add_argument('--window-seconds',type=float,default=10)
    p.add_argument('--batch-blocks',type=int,default=96)
    p.add_argument('--baselines-khz',nargs='+',type=float,default=[50,100,150,250])
    p.add_argument('--masks-khz',nargs='+',type=float,default=[0,5,10])
    p.add_argument('--force',action='store_true',help='Ignora cache e recalcula cada CU8')
    p.add_argument('--check-only',action='store_true',help='Confere metadados e tamanhos; nao processa')
    args=p.parse_args(argv)
    if args.fft<1024 or args.fft&(args.fft-1):p.error('--fft deve ser potencia de 2 >=1024')
    if min(args.rate,args.center_hz,args.window_seconds,args.batch_blocks)<=0:p.error('Parametros devem ser positivos')
    if any(x<=0 for x in args.baselines_khz) or any(x<0 for x in args.masks_khz):p.error('Baseline ou mascara invalida')
    sites={'first':args.dir_first,'repeat':args.dir_repeat}
    selected=('first','repeat') if args.only=='both' else (args.only,)
    records={}
    try:
        for s in selected:records[s]=metadados(sites[s],args.rate,args.center_hz)
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as e:
        p.error(str(e))
    for s in selected:
        for n in NAMES:
            r=records[s][n]
            print(f'{s:<6} {n:<3} | {(sites[s]/(n+".cu8")).stat().st_size/1e6:.1f} MB '
                  f'| az/el {r.get("azimuth_deg")}/{r.get("elevation_deg")} '
                  f'| {r.get("start_utc")}',flush=True)
    if args.check_only:print('Arquivos validados; nenhum CU8 foi modificado.');return 0
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    cache=out/'cache'
    step=args.rate/args.fft
    freq=args.center_hz+np.fft.fftshift(np.fft.fftfreq(args.fft,d=1/args.rate))
    smooth_bins=odd_bins(10.25,step)
    baselines=sorted(set(float(x) for x in args.baselines_khz))
    masks=sorted(set(float(x) for x in args.masks_khz))
    base_bins={b:odd_bins(b,step) for b in baselines}
    spectra={}
    for s in selected:
        spectra[s]={}
        for n in NAMES:
            spectra[s][n]=load_capture(sites[s]/(n+'.cu8'),records[s][n],cache,s,n,args)
    captures=[]
    narrow=[]
    spectra_csv=[]
    for s in selected:
        for n in NAMES:
            data=spectra[s][n]
            cidx=np.argmin(abs(freq-args.center_hz))
            dbdc=float(10*np.log10(max(data['p_dc'][cidx],EPS)/max(data['p_raw'][cidx],EPS)))
            captures.append({'campaign':s,'capture':n,'fft_blocks':int(data['n_fft']),
                             'samples':int(data['n_samples']),'discarded_tail_samples':int(data['discarded_samples']),
                             'dc_center_attenuation_db':dbdc,
                             'mean_complex_dc_i':float(data['dc_mean_i']),
                             'mean_complex_dc_q':float(data['dc_mean_q']),
                             'azimuth_deg':records[s][n].get('azimuth_deg'),
                             'elevation_deg':records[s][n].get('elevation_deg')})
            for typ,col in [('before_dc','p_raw'),('after_dc','p_dc')]:
                m=narrow_measure(freq,data[col])
                narrow.append({'campaign':s,'capture':n,'method':typ,**m})
            for f,a,b in zip(freq,data['p_raw'],data['p_dc']):
                spectra_csv.append([s,n,f,a,b])
    csv_rows(out/'individual_spectra.csv',
             ['campaign','capture','frequency_hz','power_before_dc','power_after_dc'],spectra_csv)
    csv_rows(out/'capture_audit.csv',list(captures[0]),([row[k] for k in captures[0]] for row in captures))
    csv_rows(out/'narrow_e4_peak.csv',list(narrow[0]),([row[k] for k in narrow[0]] for row in narrow))

    rows=[];pair_spectra=[];all_fig=[];window_rows=[];legacy_rows=[];warnings=[]
    # E5 original pipeline only for the second E4 campaign; optional scipy installed.
    for s in selected:
        for on in ('ON1','ON2'):
            pair=f'{on}/OFF'
            for typ,col,wcol in [('before_dc','p_raw','w_raw'),('after_dc','p_dc','w_dc')]:
                pon=spectra[s][on][col]
                poff=spectra[s]['OFF'][col]
                rr=10*np.log10(np.maximum(pon,EPS)/np.maximum(poff,EPS))
                for mask in masks:
                    for b in baselines:
                        residual=baseline_residual(freq,rr,args.center_hz,mask,smooth_bins,base_bins[b])
                        measure=broad_measure(freq,rr,residual,args.center_hz,mask)
                        rows.append({'campaign':s,'pair':pair,'method':typ,'mask_khz':mask,
                                     'baseline_khz':b,**measure})
                        if mask==5 and b==100 and typ=='after_dc':
                            all_fig.append({'campaign':s,'pair':pair,'method':typ,
                                'mask_khz':mask,'baseline_khz':b,
                                'freq':freq,'res':residual,'ratio':rr})
                            pair_spectra.extend([s,pair,typ,float(f),float(r),float(v)]
                                for f,r,v in zip(freq,rr,residual))
                if s=='repeat':
                    try:
                        base,legacy,pars=e5_legacy_like(rr,step)
                        band=(np.abs(freq-BROAD)<=20_000)
                        peak=int(np.flatnonzero(band)[np.argmax(legacy[band])])
                        legacy_rows.append({'pair':pair,'method':typ,'peak_hz_around_1420_331':float(freq[peak]),
                                            'peak_residual_db':float(legacy[peak]),
                                            'candidate_band_median_db':float(np.median(legacy[band])),
                                            **pars})
                    except ImportError:
                        warnings.append('scipy nao instalada; reanalise do metodo original E5 ignorada; os demais contrastes foram gerados.')
            n_win=min(len(spectra[s][on]['w_info']),len(spectra[s]['OFF']['w_info']))
            for wi in range(n_win):
                rr=10*np.log10(np.maximum(spectra[s][on]['w_dc'][wi],EPS)/np.maximum(spectra[s]['OFF']['w_dc'][wi],EPS))
                res=baseline_residual(freq,rr,args.center_hz,5,smooth_bins,base_bins.get(100.,next(iter(base_bins.values()))))
                m=broad_measure(freq,rr,res,args.center_hz,5)
                window_rows.append({'campaign':s,'pair':pair,'window_index':wi,
                                   'on_start_s':float(spectra[s][on]['w_info'][wi,0]),
                                   'off_start_s':float(spectra[s]['OFF']['w_info'][wi,0]),
                                   'method':'after_dc','band':'broad','mask_khz':5,
                                   'baseline_khz':100,'feature_db':m['feature_db'],
                                   'linear_sideband_fit_db':m['linear_sideband_fit_db']})
    # E5 original also computed the ratio of the mean ON power to the shared OFF.
    # Report before/after DC separately; never treat this as a third independent ON.
    if 'repeat' in selected:
        for typ,col in [('before_dc','p_raw'),('after_dc','p_dc')]:
            ps=spectra['repeat']
            average_ratio=10*np.log10(np.maximum((ps['ON1'][col]+ps['ON2'][col])/2,EPS)/
                                       np.maximum(ps['OFF'][col],EPS))
            try:
                _,filtered,pars=e5_legacy_like(average_ratio,step)
                band=np.abs(freq-BROAD)<=20_000
                ip=int(np.flatnonzero(band)[np.argmax(filtered[band])])
                legacy_rows.append({'pair':'mean_ON1_ON2/OFF (shared OFF)','method':typ,
                                    'peak_hz_around_1420_331':float(freq[ip]),
                                    'peak_residual_db':float(filtered[ip]),
                                    'candidate_band_median_db':float(np.median(filtered[band])),
                                    **pars})
            except ImportError:
                warnings.append('scipy ausente; calculos de procedimento E5 original nao realizados.')
    if not rows:raise ValueError('Nenhum contraste gerado')
    csv_rows(out/'contrasts_e4_e5.csv',list(rows[0]),([r[c] for c in rows[0]] for r in rows))
    csv_rows(out/'pair_spectra_e4_e5.csv',
        ['campaign','pair','method','frequency_hz','raw_ratio_db','residual_db'],pair_spectra)
    if window_rows:
        csv_rows(out/'windows_e4_e5.csv',list(window_rows[0]),([r[c] for c in window_rows[0]] for r in window_rows))
    if legacy_rows:
        csv_rows(out/'e5_original_method_reanalysis.csv',list(legacy_rows[0]),
                 ([r[c] for c in legacy_rows[0]] for r in legacy_rows))
    mainrows=[r for r in rows if r['method']=='after_dc' and r['mask_khz']==5 and r['baseline_khz']==100]
    narrowmain=[r for r in narrow if r['method']=='after_dc']
    directional=[]
    for s in selected:
        dic={r['capture']:r['peak_vs_local_baseline_db'] for r in narrowmain if r['campaign']==s}
        directional.append({'campaign':s,'on_mean_minus_off_peak_db':(dic['ON1']+dic['ON2'])/2-dic['OFF'],
                            'on1_db':dic['ON1'],'off_db':dic['OFF'],'on2_db':dic['ON2']})
    csv_rows(out/'direction_narrow_e4.csv',list(directional[0]),
             ([r[c] for c in directional[0]] for r in directional))
    summary={'script_version':VERSION,'generated_utc':datetime.now(timezone.utc).isoformat(),
             'input_dirs':{s:str(sites[s]) for s in selected},'output':str(out),
             'config':{'rate_hz':args.rate,'fft_size':args.fft,'resolution_hz':step,
                       'smooth_actual_khz':smooth_bins*step/1000,
                       'baselines_khz':baselines,'masks_khz':masks,
                       'broad_target_hz':BROAD,'broad_half_window_hz':20_000,'narrow_target_hz':NARROW},
             'capture_audit':captures,'broad_summary_primary':mainrows,
             'narrow_direction_diagnostic':directional,
             'e5_original_method_reanalysis':legacy_rows,
             'temporal':{s+'_'+on:{'n_windows':sum(1 for x in window_rows if x['campaign']==s and x['pair']==on),
                 'mean_db':float(np.mean([x['feature_db'] for x in window_rows if x['campaign']==s and x['pair']==on]))
                 if any(x['campaign']==s and x['pair']==on for x in window_rows) else None}
                 for s in selected for on in ('ON1/OFF','ON2/OFF')},
             'limitations':[
                'E5 is an exploratory reanalysis of the E4 repeat, not an independent data collection.',
                'E4/E5 broad candidate was selected post hoc; its positive excess is not a prospective independent confirmation.',
                'Both ON ratios within a campaign share one OFF recording; not independent contrasts.',
                'Window pairing is by elapsed time, not simultaneous sky measurements.',
                'The E5 candidate lies about 75 kHz below the receiver center; upper sideband reaches the DC frequency. Center masking matters.',
                'Per-block DC removal cannot rule out external fixed-frequency RFI or changing bandpass.',
                'Baseline choice and candidate selection influence reported excess magnitude.',
                'No absolute antenna-temperature calibration, LSR correction, or instrument health telemetry.',
                'This script does not analyze entropy or certify a TRNG.',
             ],'warnings':sorted(set(warnings))}
    dump_json(out/'summary_e4_e5_integral.json',summary)
    optional_graphs(out,all_fig,window_rows)
    (out/'README.txt').write_text(
        'E4/E5 Virgo-RNG reprocessamento integral. Sem novas aquisicoes.\n'
        'O E5 e reanalise exploratoria de E4_repeticao: nao e coleta independente.\n'
        'Use contrasts_e4_e5.csv filtrando method=after_dc, mask_khz=5, baseline_khz=100.\n'
        'Avaliacao do pico estreito: narrow_e4_peak.csv e direction_narrow_e4.csv.\n'
        'Analise temporal: windows_e4_e5.csv; janelas nao sao sessoes independentes.\n'
        'Comparacao aproximada com o metodo E5 original: e5_original_method_reanalysis.csv (se scipy).\n'
        'Nenhuma calibracao absoluta; espectros e excessos nao demonstram emissao H I nem entropia criptografica.\n'
        ,encoding='utf-8')
    pkg=zip_results(out)
    print('\n=== RESULTADOS DESCRITIVOS: faixa larga 1420.330752 MHz ===')
    for r in mainrows:print(f"{r['campaign']:<6} {r['pair']:<7} {r['feature_db']:+.5f} dB; linear={r['linear_sideband_fit_db']:+.5f} dB")
    print('=== RESULTADOS: pico estreito 1419.988565 MHz, direcional ===')
    for r in directional:print(f"{r['campaign']}: media(ON)-OFF={r['on_mean_minus_off_peak_db']:+.5f} dB")
    print(f'\nSaida: {out}\nEnvie: {pkg}\nNao envie os CU8.');return 0

if __name__=='__main__':
    try: sys.exit(main())
    except KeyboardInterrupt:
        print('\nInterrompido; repita o comando para reutilizar os caches de capturas completas.',file=sys.stderr)
        sys.exit(130)
    except (OSError,ValueError,MemoryError,KeyError) as ex:
        print('ERRO:',ex,file=sys.stderr);sys.exit(1)
