#!/usr/bin/env python3
"""Check files, recorded digests, forbidden manuscript files, and unexpected large files."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'data/provenance/FILES.json').read_text())
issues=[]
for r in manifest:
    f=root/r['path']
    if not f.is_file():issues.append(f'missing {r["path"]}');continue
    h=hashlib.sha256(f.read_bytes()).hexdigest()
    if h!=r['sha256']:issues.append(f'hash mismatch {r["path"]}')
for p in root.rglob('*'):
    if not p.is_file():continue
    if p.suffix.lower() in {'.tex','.bib','.pdf','.png','.jpg','.jpeg','.svg','.webp'}:
        issues.append(f'forbidden manuscript/figure-like artifact: {p.relative_to(root)}')
    if p.stat().st_size>100*1024*1024:issues.append(f'oversize for normal Git: {p.relative_to(root)}')
print(f'Checked {len(manifest)} archived files; problems: {len(issues)}')
for issue in issues:print('ERROR:',issue)
raise SystemExit(bool(issues))
