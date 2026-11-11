#!/usr/bin/env python3
"""Extrai trechos consecutivos I/Q de arquivos CU8 para ea_non_iid.
Não transforma, normaliza ou reordena os valores dos bytes.
"""
import argparse, hashlib, json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('files', nargs='+', type=Path)
    p.add_argument('--out', type=Path, default=Path('results/nist_non_iid'))
    p.add_argument('--rate',type=int,default=2400000)
    p.add_argument('--seconds',type=int,default=180)
    p.add_argument('--samples',type=int,default=1000000)
    p.add_argument('--offsets',type=float,nargs='+',default=[0,85,170],help='segundos desde inicio')
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for path in args.files:
        actual=path.stat().st_size
        expected=2*args.rate*args.seconds
        if actual!=expected:
            raise ValueError(f'{path}: tamanho {actual}, esperado {expected}')
        with path.open('rb') as source:
            for sec in args.offsets:
                start=round(sec*args.rate)
                if start<0 or start+args.samples>args.rate*args.seconds:
                    raise ValueError(f'{path}: trecho fora dos limites: {sec}s')
                source.seek(2*start)
                raw=source.read(2*args.samples)
                if len(raw)!=2*args.samples:
                    raise IOError('Leitura incompleta')
                for channel,offset in [('I',0),('Q',1)]:
                    data=raw[offset::2]
                    output=args.out/f'{path.stem}_{channel}_{sec:g}s.bin'
                    output.write_bytes(data)
                    digest=hashlib.sha256(data).hexdigest()
                    manifest.append({'source':str(path),'channel':channel,'offset_seconds':sec,'samples':len(data),'file':str(output),'sha256':digest,'distinct_symbols':len(set(data))})
                    print(f'{output}  symbols={len(set(data))}  sha256={digest}')
    (args.out/'manifest.json').write_text(json.dumps({'rate':args.rate,'samples_per_segment':args.samples,'segments':manifest},indent=2)+'\n')
    print('Manifest:',args.out/'manifest.json')
if __name__=='__main__':main()
