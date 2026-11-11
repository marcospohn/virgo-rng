"""Reproducible *within-recording* SP 800-90B sensitivity campaign.

No NIST estimators are implemented here. All estimates come from external official
reference executables. Segments from one recording are NOT restart experiments.
"""
import json
import re
from pathlib import Path
from .nist90b import sha256, run_nist

ESTIMATE = re.compile(r"min\(H_original,\s*8\s*[Xx×]\s*H_bitstring\):\s*([0-9]+(?:\.[0-9]+)?)")
H_ORIGINAL = re.compile(r"H_original:\s*([0-9]+(?:\.[0-9]+)?)")
H_BITSTRING = re.compile(r"H_bitstring:\s*([0-9]+(?:\.[0-9]+)?)")


def parse_estimates(stdout):
    """Read published aggregate lines, not individual estimator breakdowns."""
    fields = {}
    for name, regex in (("h_original", H_ORIGINAL),("h_bitstring",H_BITSTRING),("h_final",ESTIMATE)):
        match=regex.search(stdout)
        fields[name]=float(match.group(1)) if match else None
    return fields


def prepare_campaign(source, out_dir, *, pairs_per_segment=1000000, setup='unknown', reference_i=None, reference_q=None):
    source=Path(source)
    out_dir=Path(out_dir)
    if not source.is_file(): raise FileNotFoundError(source)
    nbytes=source.stat().st_size
    if nbytes % 2: raise ValueError('CU8 file must have an even byte count')
    total=nbytes//2
    if pairs_per_segment<1000000: raise ValueError('Segments must have at least 1,000,000 samples/channel')
    if total<3*pairs_per_segment: raise ValueError('Recording too short for 3 disjoint segments')
    if out_dir.resolve()==source.resolve(): raise ValueError('Output must differ from input')
    offsets={'beginning':0,'middle':(total-pairs_per_segment)//2,'end':total-pairs_per_segment}
    # Require disjoint ranges, even for odd total sizes.
    ranges=sorted((v,v+pairs_per_segment) for v in offsets.values())
    if any(a[1]>b[0] for a,b in zip(ranges,ranges[1:])): raise ValueError('Segments overlap')
    out_dir.mkdir(parents=True,exist_ok=True)
    inputs=[]
    for name,start in offsets.items():
        with source.open('rb') as fin:
            fin.seek(start*2)
            data=fin.read(pairs_per_segment*2)
        if len(data)!=pairs_per_segment*2: raise IOError('Short input')
        for channel,values in (('i',data[0::2]),('q',data[1::2])):
            path=out_dir/f'{name}_{channel}.bin'
            path.write_bytes(values)
            inputs.append({'id':f'{name}_{channel}','path':str(path.resolve()),'sha256':sha256(path),
                           'bytes':len(values),'channel':channel,'start_pair':start,'pairs':pairs_per_segment})
    # Full raw IQ sequence as 8-bit symbols, in acquisition order, no concatenation assumption.
    iq=out_dir/'full_iq_interleaved.bin'
    with source.open('rb') as fin, iq.open('wb') as fout:
        while data:=fin.read(1048576): fout.write(data)
    inputs.append({'id':'full_iq_interleaved','path':str(iq.resolve()),'sha256':sha256(iq),
                   'bytes':iq.stat().st_size,'channel':'iq-interleaved','start_pair':0,'pairs':total})
    references={}
    for channel,path in (('i',reference_i),('q',reference_q)):
        if path:
            obj=json.loads(Path(path).read_text())
            references[channel]={'report':str(Path(path).resolve()),'input_sha256':obj.get('input_sha256'),
                                 'status':obj.get('status'),'estimates':parse_estimates(obj.get('stdout',''))}
    manifest={'schema':'virgo-rng-nist-campaign-v1','setup':setup,'source':str(source.resolve()),
              'source_sha256':sha256(source),'total_pairs':total,'pairs_per_segment':pairs_per_segment,
              'offsets_in_pairs':offsets,'inputs':inputs,'references':references,
              'method':'Three disjoint within-recording windows; I/Q raw 8-bit; plus full raw interleaved I,Q byte sequence',
              'limitations':['Not independent acquisitions or restart tests',
                             'Do not add I and Q entropy estimates',
                             'No claim that 8-bit I/Q symbol process is IID or physically characterized',
                             'Do not use these estimates to select a cryptographic extraction rate']}
    (out_dir/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def execute_campaign(directory, *, binary, timeout=3600):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text())
    reports=[]
    for item in manifest['inputs']:
        report=directory/(item['id']+'_non_iid.json')
        run_nist(item['path'],report,binary=binary,timeout=timeout)
        reports.append(str(report))
    return reports


def summarize_campaign(directory):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text())
    rows=[]
    for item in manifest['inputs']:
        path=directory/(item['id']+'_non_iid.json')
        if path.exists():
            report=json.loads(path.read_text())
            row={'id':item['id'],'status':report.get('status'), 'input_hash_matches':report.get('input_sha256')==item['sha256'],
                 'estimates':parse_estimates(report.get('stdout',''))}
        else: row={'id':item['id'],'status':'not_run','input_hash_matches':None,'estimates':None}
        rows.append(row)
    return {'schema':'virgo-rng-nist-campaign-summary-v1','source_sha256':manifest['source_sha256'],
            'reference_results':manifest.get('references',{}),'results':rows,
            'warning':'Within-recording sensitivity analysis only; not restart validation or certification'}
