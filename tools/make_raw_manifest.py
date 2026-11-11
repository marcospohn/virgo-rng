#!/usr/bin/env python3
"""Generate SHA-256 manifest of local CU8 files without modifying or uploading them."""
import argparse,hashlib,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('--out',type=Path,default=Path('raw_manifest.json'))
    args=p.parse_args()
    if not args.directory.is_dir():p.error('directory not found')
    results=[]
    for f in sorted(args.directory.rglob('*.cu8')):
        h=hashlib.sha256()
        with f.open('rb') as inp:
            for b in iter(lambda:inp.read(4*1024*1024),b''):h.update(b)
        results.append({'filename':f.name,'relative_path':f.relative_to(args.directory).as_posix(),
                        'size_bytes':f.stat().st_size,'sha256':h.hexdigest()})
    args.out.write_text(json.dumps({'files':results,'format':'unsigned-8-bit interleaved I/Q'},indent=2)+'\n')
    print(f'{len(results)} files, manifest at {args.out}')
if __name__=='__main__':main()
