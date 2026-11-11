"""Reproducible, fail-explicit CU8 research workflow. Not a cryptographic certification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from .persistence122 import analyze as persistence_analyze

SCHEMA = 'virgo-rng-lab-v2'
DEFAULT = {'rate':2400000,'freq':1420405752,'gain':30.0,'setup':'unknown',
           'pairs_per_window':65536,'windows':120,'lags':[8,41],
           'max_analysis_bytes':8000000}
VALID_SETUP={'indoor-dipole','external-antenna','50ohm-termination','other','unknown'}

def config_load(path):
    cfg=DEFAULT.copy()
    if path:
        user=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(user,dict) or set(user)-set(DEFAULT):
            raise ValueError('Unknown configuration keys or invalid JSON object')
        cfg.update(user)
    if not isinstance(cfg['rate'],int) or cfg['rate']<=0 or not isinstance(cfg['freq'],int) or cfg['freq']<=0:
        raise ValueError('rate/freq must be positive integers')
    if not isinstance(cfg['gain'],(int,float)) or not (-10<=cfg['gain']<=60):
        raise ValueError('gain outside supported configuration bounds')
    if cfg['setup'] not in VALID_SETUP: raise ValueError('Invalid setup')
    if not isinstance(cfg['pairs_per_window'],int) or cfg['pairs_per_window']<128:
        raise ValueError('pairs_per_window must be >=128')
    if not isinstance(cfg['windows'],int) or cfg['windows']<2: raise ValueError('windows must be >=2')
    if not isinstance(cfg['lags'],list) or not cfg['lags'] or any(type(x)!=int or x<1 or x>=cfg['pairs_per_window'] for x in cfg['lags']):
        raise ValueError('Invalid lags')
    if not isinstance(cfg['max_analysis_bytes'],int) or cfg['max_analysis_bytes']<4096:
        raise ValueError('max_analysis_bytes must be >=4096')
    return cfg

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    try:
        tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

def study(path, out, cfg, full=False):
    path=Path(path).resolve();out=Path(out).resolve()
    if not path.is_file():raise ValueError('Input file not found')
    if path.stat().st_size%2 or path.stat().st_size<cfg['pairs_per_window']*4:
        raise ValueError('Input must be even-length CU8 with at least two complete windows')
    if out==path or out in path.parents:raise ValueError('Invalid output path')
    if out.exists() and any(out.iterdir()):raise ValueError('Output directory must be empty/new to avoid overwrites')
    out.mkdir(parents=True,exist_ok=True)
    manifest={'schema':SCHEMA,'created_utc':datetime.now(timezone.utc).isoformat(),
              'input':str(path),'input_bytes':path.stat().st_size,'input_sha256':sha256(path),
              'configuration':cfg,'steps':{},'limitations':['Not NIST SP 800-90B certification',
              'Correlations do not estimate min-entropy','RF source attribution requires controlled measurements']}
    atomic_json(out/'manifest.json',manifest)
    try:
        rep=persistence_analyze(path,out/'persistence',rate=cfg['rate'],windows=cfg['windows'],
                                pairs=cfg['pairs_per_window'],lags=tuple(cfg['lags']),full=full)
        manifest['steps']['persistence']={'status':'ok','coverage':rep['coverage']}
        # Explicitly bounded extra analyses; full-length persistence remains available separately.
        n=min(cfg['max_analysis_bytes'],path.stat().st_size)
        if n%2:n-=1
        with path.open('rb') as f: sample=f.read(n)
        from collections import Counter
        import math
        channels={}
        for label,offset in [('I',0),('Q',1)]:
            x=sample[offset::2]; counts=Counter(x); total=len(x)
            pmax=max(counts.values())/total
            h=-sum((v/total)*math.log2(v/total) for v in counts.values())
            channels[label]={'sample_count':total,'distinct_symbols':len(counts),
                             'shannon_bits_per_8bit_symbol':h,
                             'most_frequent_symbol_probability':pmax,
                             'naive_most_frequent_bound_bits':-math.log2(pmax)}
        atomic_json(out/'descriptive_entropy.json',{'schema':SCHEMA,'analyzed_bytes':n,
            'channels':channels,'warning':'Naive most-frequent-symbol bound is NOT validated min-entropy for dependent data.'})
        manifest['steps']['descriptive_entropy']={'status':'ok','analyzed_bytes':n}
        manifest['status']='completed'
    except Exception as exc:
        manifest['status']='failed';manifest['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:atomic_json(out/'manifest.json',manifest)
    return manifest

def main(argv=None):
    p=argparse.ArgumentParser(description='Virgo-RNG 2.0 reproducible lab (research-only)')
    sub=p.add_subparsers(dest='cmd',required=True)
    init=sub.add_parser('init',help='Create validated example configuration')
    init.add_argument('--out',type=Path,default=Path('virgo_config.json'))
    st=sub.add_parser('study',help='Immutable CU8 input -> provenance, persistence, descriptive entropy')
    st.add_argument('file',type=Path);st.add_argument('--out-dir',type=Path,required=True)
    st.add_argument('--config',type=Path);st.add_argument('--full',action='store_true')
    cap=sub.add_parser('capture',help='Delegate bounded RTL-SDR capture to existing stable CLI')
    cap.add_argument('--out',type=Path,required=True);cap.add_argument('--report',type=Path,required=True)
    cap.add_argument('--seconds',type=float,default=10);cap.add_argument('--config',type=Path)
    legacy=sub.add_parser('legacy',help='Run original virgo-rng command, preserving all prior research modes')
    legacy.add_argument('arguments',nargs=argparse.REMAINDER)
    args=p.parse_args(argv)
    try:
        if args.cmd=='init':
            if args.out.exists():raise ValueError('Refusing to overwrite existing config')
            atomic_json(args.out,DEFAULT);print(args.out)
        elif args.cmd=='study':
            result=study(args.file,args.out_dir,config_load(args.config),args.full)
            print(json.dumps({'status':result['status'],'output':str(args.out_dir),'coverage':result['steps']['persistence']['coverage']},indent=2))
        elif args.cmd=='capture':
            cfg=config_load(args.config)
            if args.seconds<=0:raise ValueError('seconds must be positive')
            cmd=[sys.executable,'-m','virgo_rng.cli','stream','--seconds',str(args.seconds),
                 '--rate',str(cfg['rate']),'--freq',str(cfg['freq']),'--gain',str(cfg['gain']),
                 '--setup',cfg['setup'],'--out',str(args.out),'--report',str(args.report)]
            subprocess.run(cmd,check=True)
        else:
            if not args.arguments:raise ValueError('Supply original virgo-rng arguments')
            subprocess.run([sys.executable,'-m','virgo_rng.cli',*args.arguments],check=True)
    except (ValueError,OSError,subprocess.CalledProcessError) as e:
        p.exit(2,f'ERROR: {e}\n')

if __name__=='__main__':main()
