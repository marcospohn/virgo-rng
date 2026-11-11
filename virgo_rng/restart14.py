"""Strict wrapper for official NIST SP 800-90B ea_restart (non-IID)."""
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path
from .nist90b import sha256

def evaluate(directory, *, binary='ea_restart', h_i=None, h_q=None, timeout=3600,
             ack_physical_restarts=False, report_dir=None):
    directory=Path(directory).resolve()
    if Path(binary).name != 'ea_restart':
        raise ValueError('Expected official ea_restart executable')
    if not ack_physical_restarts:
        raise ValueError('Physical restarts must be explicitly attested; cannot infer from files')
    if h_i is None or not math.isfinite(h_i) or not 0 < h_i <= 8:
        raise ValueError('H_I must be a finite, positive initial entropy estimate <= 8')
    if h_q is not None and (not math.isfinite(h_q) or not 0 < h_q <= 8):
        raise ValueError('H_Q must be a finite, positive initial entropy estimate <= 8')
    if timeout <= 0:
        raise ValueError('Timeout must be positive')
    exe=shutil.which(binary) if os.sep not in binary else str(Path(binary).resolve())
    if not exe or not Path(exe).is_file():
        raise FileNotFoundError(f'Build official NIST ea_restart: {binary}')
    cfg=json.loads((directory/'config.json').read_text())
    manifest=json.loads((directory/'restart_manifest.json').read_text())
    if cfg['runs_requested']!=1000 or cfg['samples_per_run']!=1000:
        raise ValueError('NIST restart assessment requires exactly 1000 restarts x 1000 samples')
    if manifest['runs']!=1000 or manifest['samples_per_run']!=1000:
        raise ValueError('Matrix dimensions incorrect')
    if sha256(directory/'config.json') != manifest['source_config_sha256']:
        raise ValueError('Configuration changed after matrix creation')
    if cfg.get('reset_mode') not in ('manual-operator-attested','external-command-unverified'):
        raise ValueError('Missing reset mode provenance')
    records=[json.loads(x) for x in (directory/'runs.jsonl').read_text().splitlines() if x.strip()]
    if len(records)!=1000 or any(r.get('run')!=i or not r.get('ok') for i,r in enumerate(records)):
        raise ValueError('Incomplete acquisition journal')
    # Verify all original captures before trusting the matrix. Protect against stale or edited files.
    for rec in records:
        f=directory/rec['file']
        if not f.is_file() or f.stat().st_size!=2000 or sha256(f)!=rec['sha256']:
            raise ValueError(f'Original capture integrity failed: {f}')
    paths={}
    for channel in ('i','q'):
        f=directory/f'restart_{channel}.bin'
        info=manifest['outputs'][channel]
        if not f.is_file() or f.stat().st_size!=1000000 or info['bytes']!=1000000 or sha256(f)!=info['sha256']:
            raise ValueError(f'Restart matrix integrity failed: {f}')
        paths[channel]=f
    target=Path(report_dir).resolve() if report_dir else directory/'nist_restart_reports'
    target.mkdir(parents=True,exist_ok=True)
    reports={}
    for channel,f in paths.items():
        # Run from the data directory, using a relative file name, as specified by ea_restart.
        current_h = h_i if channel == 'i' or h_q is None else h_q
        cmd=[str(Path(exe).resolve()),'-n',f.name,'8',format(current_h,'.12g')]
        start=time.monotonic()
        try:
            proc=subprocess.run(cmd,cwd=directory,capture_output=True,text=True,timeout=timeout)
            outcome={'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,'timed_out':False}
        except subprocess.TimeoutExpired as e:
            def dec(v): return v.decode(errors='replace') if isinstance(v,bytes) else (v or '')
            outcome={'returncode':None,'stdout':dec(e.stdout),'stderr':dec(e.stderr),'timed_out':True}
        report={'schema':'virgo-rng-nist-restart-report-v1','channel':channel,
                'status':'completed' if outcome['returncode']==0 else 'failed',
                'command':cmd,'cwd':str(directory),'tool_sha256':sha256(exe),
                'input_sha256':sha256(f),'h_i':current_h,'mode':'non-IID (-n)',
                'elapsed_seconds':round(time.monotonic()-start,3),
                'physical_restart_attestation':'operator-provided, not verified by software',
                'warning':'A completed process does NOT imply passing NIST sanity or validation tests; inspect full stdout/stderr.',
                **outcome}
        output=target/f'restart_{channel}_nist.json'
        output.write_text(json.dumps(report,indent=2)+'\n')
        reports[channel]=str(output)
        if report['status']!='completed':
            raise RuntimeError(f'ea_restart failed for {channel}: {output}')
    return reports
