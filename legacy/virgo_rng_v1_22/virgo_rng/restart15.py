"""Offline integrity audit for restart collections. No claim of physical reset."""
import json
from pathlib import Path
from .nist90b import sha256


def audit(directory, *, require_full=False):
    directory=Path(directory)
    errors=[]
    cfg_path=directory/'config.json'
    journal_path=directory/'runs.jsonl'
    if not cfg_path.is_file() or not journal_path.is_file():
        raise ValueError('Missing config.json or runs.jsonl')
    cfg=json.loads(cfg_path.read_text())
    expected=cfg['runs_requested']; samples=cfg['samples_per_run']
    if require_full and (expected!=1000 or samples!=1000):
        errors.append('NIST restart dimensions must be 1000 x 1000')
    records=[]
    for line_no,line in enumerate(journal_path.read_text().splitlines(),1):
        if not line.strip(): continue
        try: records.append(json.loads(line))
        except json.JSONDecodeError: errors.append(f'Invalid JSON journal line {line_no}')
    if len(records)!=expected:
        errors.append(f'Incomplete journal: {len(records)} of {expected} runs')
    for index,record in enumerate(records):
        if record.get('run')!=index: errors.append(f'Unexpected run index at position {index}')
        name=record.get('file','')
        if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.cu8'):
            errors.append(f'Unsafe/invalid file name at run {index}'); continue
        f=directory/name
        if not f.is_file(): errors.append(f'Missing capture {name}');continue
        if f.stat().st_size!=2*samples or record.get('bytes')!=2*samples:
            errors.append(f'Wrong capture length: {name}')
        if sha256(f)!=record.get('sha256'):
            errors.append(f'Hash mismatch: {name}')
        if not record.get('ok') or record.get('returncode')!=0:
            errors.append(f'Capture marked unsuccessful: {name}')
    manifest_path=directory/'restart_manifest.json'
    matrix_checks={}
    if manifest_path.exists():
        m=json.loads(manifest_path.read_text())
        if m.get('source_config_sha256')!=sha256(cfg_path): errors.append('Config hash mismatch')
        for channel in ('i','q'):
            f=directory/f'restart_{channel}.bin'
            info=m.get('outputs',{}).get(channel,{})
            valid=f.is_file() and f.stat().st_size==expected*samples and sha256(f)==info.get('sha256')
            matrix_checks[channel]=valid
            if not valid: errors.append(f'Matrix invalid: {channel}')
    else:
        matrix_checks={'i':False,'q':False}
    return {'schema':'virgo-rng-restart-audit-v1','runs_expected':expected,
            'runs_recorded':len(records),'samples_per_run':samples,
            'reset_mode':cfg.get('reset_mode'),'matrix_checks':matrix_checks,
            'integrity_ok':not errors,'errors':errors,
            'physical_restart_verified':False,
            'warning':'Hashes verify data integrity, not physical power cycling, first-sample fidelity, or NIST compliance.'}
