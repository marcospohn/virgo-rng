#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reprocessamento SOMENTE de CU8 originais E1 (2 campanhas) e E3.

Exemplos:
  python virgo_e1_e3_reprocessar_integral.py --check-only
  python virgo_e1_e3_reprocessar_integral.py --only e3
  python virgo_e1_e3_reprocessar_integral.py --only all

Nao captura dados, nao requer RTL-SDR, nao altera CU8. Retoma por captura.
O script usa metadados resumidos originais dos ZIPs E1_results.zip,
E1_repeticao.zip e E3_resultados.zip (09/11/2026) se faltar metadata.json.
Todos os resultados sao relativos/nao calibrados; nao provam origem HI.
"""
from __future__ import annotations
import argparse, csv, json, math, os, zipfile
from pathlib import Path
import numpy as np

VERSION='1.0.0'
RATE=2_400_000
CENTER=1_420_405_752
NARROW=1_419_988_565
EPS=1e-24

# BEGIN_EMBEDDED_METADATA
EMBEDDED = {'first': [{'name': 'A1', 'bytes': 864000000, 'seconds': 180, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': '50ohm', 'start_utc': '2026-11-09T15:37:25.700915+00:00', 'azimuth_deg': '', 'elevation_deg': ''}, {'name': 'ON1', 'bytes': 864000000, 'seconds': 180, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': 'antenna', 'start_utc': '2026-11-09T15:46:26.660300+00:00', 'azimuth_deg': '102', 'elevation_deg': '57'}, {'name': 'OFF', 'bytes': 864000000, 'seconds': 180, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': 'antenna', 'start_utc': '2026-11-09T15:53:14.592148+00:00', 'azimuth_deg': '323', 'elevation_deg': '57'}, {'name': 'ON2', 'bytes': 864000000, 'seconds': 180, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': 'antenna', 'start_utc': '2026-11-09T16:00:10.601772+00:00', 'azimuth_deg': '102', 'elevation_deg': '57'}, {'name': 'A2', 'bytes': 864000000, 'seconds': 180, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': '50ohm', 'start_utc': '2026-11-09T16:05:35.920189+00:00', 'azimuth_deg': '', 'elevation_deg': ''}], 'repeat': [{'name': 'A1', 'bytes': 864000000, 'seconds': 180, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': '50ohm', 'start_utc': '2026-11-09T16:19:18.006897+00:00', 'azimuth_deg': '', 'elevation_deg': ''}, {'name': 'ON1', 'bytes': 864000000, 'seconds': 180, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': 'antenna', 'start_utc': '2026-11-09T16:25:02.381632+00:00', 'azimuth_deg': '101', 'elevation_deg': '67'}, {'name': 'OFF', 'bytes': 864000000, 'seconds': 180, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': 'antenna', 'start_utc': '2026-11-09T16:30:31.542189+00:00', 'azimuth_deg': '320', 'elevation_deg': '67'}, {'name': 'ON2', 'bytes': 864000000, 'seconds': 180, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': 'antenna', 'start_utc': '2026-11-09T16:36:05.150415+00:00', 'azimuth_deg': '101', 'elevation_deg': '67'}, {'name': 'A2', 'bytes': 864000000, 'seconds': 180, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': '50ohm', 'start_utc': '2026-11-09T16:40:29.788609+00:00', 'azimuth_deg': '', 'elevation_deg': ''}], 'e3': [{'name': 'A1', 'bytes': 288000000, 'seconds': 60, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': 'Carga 50 ohms', 'start_utc': '2026-11-09T17:04:12.443061+00:00'}, {'name': 'ON', 'bytes': 288000000, 'seconds': 60, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': 'Antena', 'start_utc': '2026-11-09T17:06:05.055103+00:00'}, {'name': 'A2', 'bytes': 288000000, 'seconds': 60, 'center_hz': 1420405752, 'sample_rate': 2400000, 'condition': 'Carga 50 ohms', 'start_utc': '2026-11-09T17:07:44.857237+00:00'}]}
# END_EMBEDDED_METADATA

DIR_DEFAULTS={'first':'results/E1_20261109','repeat':'results/E1_20261109_repeticao',
              'e3':'results/E3_50ohm_antena'}
CAPTURES={'first':('A1','ON1','OFF','ON2','A2'),
          'repeat':('A1','ON1','OFF','ON2','A2'),
          'e3':('A1','ON','A2')}

def save_json(path, obj):
    tmp=path.with_name('.'+path.name+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    os.replace(tmp,path)

def save_csv(path,rows,fields):
    tmp=path.with_name('.'+path.name+'.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as file:
        w=csv.DictWriter(file,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    os.replace(tmp,path)

def get_rec(name,root,labels):
    # If metadata is present, prefer its records. E1 original instead has
    # campaign.json and one JSON for each capture; both formats supported.
    f=root/'metadata.json'
    if f.exists():
        rec=json.loads(f.read_text())
        if isinstance(rec,dict) and 'captures' in rec: rec=rec['captures']
        if not isinstance(rec,list):raise ValueError(f'{f}: esperado array de capturas')
        records={r.get('capture',r.get('name',r.get('tag'))):r for r in rec}
        src=str(f)
    elif (root/'campaign.json').is_file() and all((root/(k+'.json')).exists() for k in labels):
        records={}
        for k in labels:
            r=json.loads((root/(k+'.json')).read_text())
            records[k]=dict(name=k,bytes=r.get('expected_bytes',r.get('actual_bytes')),
                            seconds=180,center_hz=CENTER,sample_rate=RATE,condition=r.get('condition'),
                            start_utc=r.get('start_utc'),azimuth_deg=r.get('azimuth_deg'),
                            elevation_deg=r.get('elevation_deg'))
        src='metadados JSON locais'
    else:
        records={r['name']:r for r in EMBEDDED[name]}
        src='copia resumida dos ZIPs originais, embutida no script'
    norm={}
    for k in labels:
        if k not in records:raise ValueError(f'{name}: metadados nao incluem {k} ({src})')
        r=records[k]
        rec=dict(name=k,
          bytes=int(r.get('bytes',r.get('expected_bytes',r.get('actual_bytes',0)))),
          seconds=float(r.get('seconds',r.get('duration_s',180 if name!='e3' else 60))),
          center_hz=int(r.get('center_hz',r.get('frequency_hz',CENTER))),
          sample_rate=int(r.get('sample_rate',r.get('rate_sps',RATE))),
          condition=r.get('condition',r.get('connection','')),
          start_utc=r.get('start_utc',''),azimuth_deg=r.get('azimuth_deg',''),
          elevation_deg=r.get('elevation_deg',''))
        if rec['center_hz']!=CENTER or rec['sample_rate']!=RATE:
            raise ValueError(f'{name} {k}: frequencia/taxa nao coincidem com o protocolo')
        fp=root/(k+'.cu8')
        if not fp.is_file():raise ValueError(f'Arquivo ausente: {fp}. Localize com: find results -type f -name "*.cu8"')
        bytes_=fp.stat().st_size
        if bytes_!=rec['bytes'] or bytes_%2 or abs(bytes_/(2*RATE)-rec['seconds'])>0.1:
            raise ValueError(f'{fp}: tamanho invalido; encontrado {bytes_}; esperado {rec["bytes"]}')
        norm[k]=rec
    return norm,src

def shannon(counts):
    n=float(counts.sum());nz=counts[counts>0].astype(np.float64)/n
    return float(-np.sum(nz*np.log2(nz)))

def minimum_entropy(counts):
    return float(-math.log2(np.max(counts)/float(counts.sum())))

def run_fft(path,fft,rate,window_seconds,batch_blocks):
    """Stream full CU8; sum Hann FFT powers, blockwise DC subtraction;
    gather 10s segment powers and I/Q statistics from all samples.
    """
    u=np.memmap(path,dtype=np.uint8,mode='r')
    N=u.size//2; nblocks=N//fft; nwinblocks=max(1,round(rate*window_seconds/fft))
    if nblocks<4:raise ValueError(f'{path}: captura curta demais')
    Hann=np.hanning(fft).astype(np.float32)
    Hann_fft=np.fft.fft(Hann).astype(np.complex64)
    sum_raw=np.zeros(fft,np.float64);sum_dc=np.zeros(fft,np.float64)
    wraw=[];wdc=[];winmeta=[]
    for start in range(0,nblocks,nwinblocks):
        stop=min(start+nwinblocks,nblocks)
        raw_=np.zeros(fft,np.float64);dc_=np.zeros(fft,np.float64)
        hi=np.zeros(256,np.int64);hq=np.zeros(256,np.int64)
        s1=np.zeros(2,np.float64);s2=np.zeros(2,np.float64)
        for b in range(start,stop,batch_blocks):
            nr=min(batch_blocks,stop-b)
            a=b*fft*2
            batch=np.asarray(u[a:a+nr*fft*2]).reshape(nr,fft,2)
            ii=batch[:,:,0];qq=batch[:,:,1]
            hi+=np.bincount(ii.ravel(),minlength=256)
            hq+=np.bincount(qq.ravel(),minlength=256)
            s1[0]+=float(np.sum(ii,dtype=np.float64));s1[1]+=float(np.sum(qq,dtype=np.float64))
            s2[0]+=float(np.sum(ii.astype(np.float32)**2,dtype=np.float64))
            s2[1]+=float(np.sum(qq.astype(np.float32)**2,dtype=np.float64))
            iq=(ii.astype(np.float32)-127.5)+1j*(qq.astype(np.float32)-127.5)
            mu=iq.mean(axis=1)
            fourier=np.fft.fft(iq*Hann,axis=1)
            raw_+=np.sum(np.abs(fourier)**2,axis=0)
            fourier-=mu[:,None]*Hann_fft[None,:]
            dc_+=np.sum(np.abs(fourier)**2,axis=0)
        blocks=stop-start
        sum_raw+=raw_;sum_dc+=dc_
        wraw.append(np.fft.fftshift(raw_/blocks))
        wdc.append(np.fft.fftshift(dc_/blocks))
        n=blocks*fft
        st=s1/n
        sd=np.sqrt(np.maximum(s2/n-st**2,0))
        winmeta.append({'start_s':start*fft/rate,'stop_s':stop*fft/rate,
                        'n_fft_blocks':blocks,'sample_pairs':n,
                        'mean_i':float(st[0]),'mean_q':float(st[1]),
                        'std_i':float(sd[0]),'std_q':float(sd[1]),
                        'shannon_i_bits':shannon(hi),'shannon_q_bits':shannon(hq),
                        'min_entropy_i_bits':minimum_entropy(hi),
                        'min_entropy_q_bits':minimum_entropy(hq)})
    del u
    return dict(p_raw=np.fft.fftshift(sum_raw/nblocks),p_dc=np.fft.fftshift(sum_dc/nblocks),
                w_raw=np.stack(wraw),w_dc=np.stack(wdc),
                winmeta_json=json.dumps(winmeta), nblocks=nblocks, n_samples=N,
                tail_samples=N-nblocks*fft)

def cache_capture(path, rec, output, group,name,args):
    stamp=path.stat()
    fingerprint={'path':str(path.resolve()),'size':stamp.st_size,'mtime_ns':stamp.st_mtime_ns,
                 'version':VERSION,'fft':args.fft,'rate':args.rate,'win_s':args.window_seconds}
    cache=output/'cache';cache.mkdir(exist_ok=True,parents=True)
    f=cache/f'{group}_{name}.npz'
    if f.exists() and not args.force:
        try:
            with np.load(f,allow_pickle=False) as z:
                if json.loads(str(z['fingerprint'].item()))==fingerprint:
                    print(f'  {group}/{name}: cache valido — pulando.',flush=True)
                    return {k:z[k].copy() for k in z.files if k!='fingerprint'}
        except (ValueError,KeyError,OSError,EOFError):pass
    print(f'  {group}/{name}: processando {stamp.st_size/1e6:.1f} MB',flush=True)
    data=run_fft(path,args.fft,args.rate,args.window_seconds,args.batch_blocks)
    temp=cache/f'.{group}_{name}.tmp.npz'
    with temp.open('wb') as stream:np.savez_compressed(stream,fingerprint=json.dumps(fingerprint),**data)
    os.replace(temp,f)
    return data

def narrow_feature(freq,power,center=NARROW):
    mask=np.abs(freq-center)<=1500
    side=(np.abs(freq-center)>=10000)&(np.abs(freq-center)<=35000)
    p=power[mask];idx=int(np.argmax(p));index=np.flatnonzero(mask)[idx]
    return dict(peak_hz=float(freq[index]),peak_excess_db=float(10*np.log10(max(power[index],EPS)/max(np.median(power[side]),EPS))))

def relative_peak(freq, power_A, power_B,center=NARROW):
    r=10*np.log10(np.maximum(power_A,EPS)/np.maximum(power_B,EPS))
    mask=np.abs(freq-center)<=1500
    side=(np.abs(freq-center)>=10000)&(np.abs(freq-center)<=35000)
    return float(np.median(r[mask])-np.median(r[side]))

def plot_results(out,stats,contrasts, freq,specs):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('matplotlib nao instalado; gerados CSV/JSON sem graficos');return
    fig,axs=plt.subplots(2,1,figsize=(10,7),constrained_layout=True)
    for group,recordings in specs.items():
        for key,data in recordings.items():
            if key.startswith('A') and group!='e3':continue
            m=np.abs(freq-NARROW)<50_000
            db=10*np.log10(np.maximum(data['p_dc'],EPS))
            db=db-np.median(db[m])
            axs[0].plot(freq[m]/1e6,db[m],lw=.8,label=f'{group}:{key}')
    axs[0].axvline(NARROW/1e6,ls='--',color='black',lw=.7)
    axs[0].set(title='Candidate narrow feature, spectra after blockwise DC correction',xlabel='Absolute RF frequency (MHz)',ylabel='Relative spectral level (dB)')
    axs[0].legend(fontsize=7,ncol=3)
    for group,recordings in specs.items():
        for key,data in recordings.items():
            win=json.loads(str(data['winmeta_json']))
            axs[1].plot([w['start_s'] for w in win],[w['shannon_i_bits'] for w in win],marker='.',ms=3,lw=.8,label=f'{group}:{key}')
    axs[1].set(title='Empirical marginal Shannon entropy I per 10s window',xlabel='Time within capture (s)',ylabel='Shannon I (bits/sample)')
    axs[1].legend(fontsize=7,ncol=3)
    fig.savefig(out/'e1_e3_reanalysis.png',dpi=160);plt.close(fig)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--dir-first',type=Path,default=Path(DIR_DEFAULTS['first']))
    p.add_argument('--dir-repeat',type=Path,default=Path(DIR_DEFAULTS['repeat']))
    p.add_argument('--dir-e3',type=Path,default=Path(DIR_DEFAULTS['e3']))
    p.add_argument('--only',choices=['first','repeat','e3','e1','all'],default='all')
    p.add_argument('--output',type=Path,default=Path('results/E1_E3_reprocessing'))
    p.add_argument('--rate',type=int,default=RATE)
    p.add_argument('--fft',type=int,default=8192)
    p.add_argument('--window-seconds',type=float,default=10.0)
    p.add_argument('--batch-blocks',type=int,default=64)
    p.add_argument('--force',action='store_true')
    p.add_argument('--check-only',action='store_true')
    args=p.parse_args(argv)
    if args.fft<1024 or args.fft&(args.fft-1):p.error('FFT deve ser potencia de dois (>=1024)')
    if args.rate!=RATE:p.error('Taxa diferente daquela utilizada na campanha; use 2400000')
    if args.window_seconds<=0 or args.batch_blocks<=0:p.error('Parametros invalidos')
    groups={'first':args.dir_first,'repeat':args.dir_repeat,'e3':args.dir_e3}
    selected=('first','repeat','e3') if args.only=='all' else (('first','repeat') if args.only=='e1' else (args.only,))
    info={}
    try:
        for g in selected:
            info[g],source=get_rec(g,groups[g],CAPTURES[g])
            print(f'{g}: {source}',flush=True)
            for name in CAPTURES[g]:
                r=info[g][name]
                print(f'  {groups[g]}/{name}.cu8 ({r["bytes"]:,} bytes, {r["seconds"]:g}s)',flush=True)
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as ex:
        p.error(str(ex))
    if args.check_only:
        print('Validacao finalizada. Nenhum arquivo foi modificado.');return
    out=args.output;out.mkdir(exist_ok=True,parents=True)
    freq=CENTER+np.fft.fftshift(np.fft.fftfreq(args.fft,1/args.rate))
    data={}
    for g in selected:
        data[g]={}
        for name in CAPTURES[g]:
            data[g][name]=cache_capture(groups[g]/f'{name}.cu8',info[g][name],out,g,name,args)
    statrows=[];winrows=[];spectrarows=[];contrasts=[]
    for g in selected:
        for name in CAPTURES[g]:
            d=data[g][name]
            atdc=narrow_feature(freq,d['p_dc']);atraw=narrow_feature(freq,d['p_raw'])
            cx=int(np.argmin(abs(freq-CENTER)))
            statrows.append(dict(campaign=g,capture=name,**atdc,
                  peak_excess_before_dc_db=atraw['peak_excess_db'],
                  center_dc_attenuation_db=float(10*np.log10(max(d['p_dc'][cx],EPS)/max(d['p_raw'][cx],EPS))),
                  fft_blocks=int(d['nblocks']),sample_pairs=int(d['n_samples']),
                  discarded_tail_samples=int(d['tail_samples']),
                  start_utc=info[g][name]['start_utc'],
                  condition=info[g][name]['condition'],
                  azimuth_deg=info[g][name].get('azimuth_deg',''),
                  elevation_deg=info[g][name].get('elevation_deg','')))
            for i,w in enumerate(json.loads(str(d['winmeta_json']))):
                small=narrow_feature(freq,d['w_dc'][i])
                winrows.append(dict(campaign=g,capture=name,window_index=i,
                                    local_narrow_peak_db=small['peak_excess_db'],
                                    **w))
            for f,pr,pdc in zip(freq,d['p_raw'],d['p_dc']):
                spectrarows.append(dict(campaign=g,capture=name,frequency_hz=float(f),
                                       power_before_dc=float(pr),power_after_dc=float(pdc)))
        refnames=('OFF',) if g!='e3' else ('A1','A2')
        onnames=('ON1','ON2') if g!='e3' else ('ON',)
        for on in onnames:
            for off in refnames:
                d1=data[g][on];d2=data[g][off]
                for method,col,wcol in [('before_dc','p_raw','w_raw'),('after_dc','p_dc','w_dc')]:
                    nr=relative_peak(freq,d1[col],d2[col])
                    contrasts.append(dict(campaign=g,pair=on+'/'+off,method=method,window_index='full',
                                          relative_narrow_peak_db=nr,notes='Descriptive; no calibration'))
                    nw=min(len(d1[wcol]),len(d2[wcol]))
                    for t in range(nw):
                        rr=relative_peak(freq,d1[wcol][t],d2[wcol][t])
                        contrasts.append(dict(campaign=g,pair=on+'/'+off,method=method,
                                              window_index=t,relative_narrow_peak_db=rr,
                                              notes='Non-simultaneous windows; not independent sky replications'))
    save_csv(out/'capture_audit.csv',statrows,list(statrows[0]))
    save_csv(out/'window_statistics.csv',winrows,list(winrows[0]))
    save_csv(out/'individual_spectra.csv',spectrarows,list(spectrarows[0]))
    save_csv(out/'narrow_contrasts.csv',contrasts,list(contrasts[0]))
    allstat=dict(version=VERSION,source='Original E1/E3 CU8 processed on local computer',
       candidates_hz=[NARROW],fft=args.fft,rate_hz=args.rate,
       n_captures=len(statrows),total_fft_blocks=sum(r['fft_blocks'] for r in statrows),
       total_complex_samples=sum(r['sample_pairs'] for r in statrows),
       warnings=['No astronomical detection inferred from narrow spike',
                 'E1 ON/OFF are sequential not simultaneous and no randomization',
                 'E3 matched load is an instrumental control, not a sky OFF reference',
                 'Window comparisons are descriptive, not independent sky measurements'],
       capture_audit=statrows,
       full_contrasts=[r for r in contrasts if r['window_index']=='full'])
    save_json(out/'summary_e1_e3.json',allstat)
    plot_results(out,statrows,contrasts,freq,data)
    zip_path=out.parent/'E1_E3_reprocessamento_resultados.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.iterdir()):
            if f.is_file() and f.suffix in ('.csv','.json','.png'):
                z.write(f,f.name)
    print('\nConcluido. Arquivo para enviar:',zip_path,flush=True)

if __name__=='__main__':main()
