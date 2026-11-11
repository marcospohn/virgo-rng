"""Restart data acquisition and provenance; NOT a SP 800-90B restart validation.

Each capture starts a fresh rtl_sdr process AFTER an operator-verified physical
power cycle or externally supplied reset action. A new process alone is NOT a
physical power cycle. No samples are deliberately discarded by this module.
"""
import json
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from .nist90b import sha256


def _now():
    return datetime.now(timezone.utc).isoformat()


def collect(directory, *, runs=1000, samples=1000, rate=2400000,
            freq=1420405752, gain=30, device=0, rtl_binary='rtl_sdr',
            restart_command=None, manual=False, setup='unknown', timeout=30):
    if runs < 1 or samples < 1 or rate <= 0 or freq <= 0 or timeout <= 0:
        raise ValueError('Invalid acquisition parameters')
    if manual == bool(restart_command):
        raise ValueError('Choose exactly one: --manual or --restart-command')
    binary=shutil.which(rtl_binary) if '/' not in rtl_binary else str(Path(rtl_binary).resolve())
    if not binary or not Path(binary).is_file():
        raise FileNotFoundError('rtl_sdr executable not found')
    directory=Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError('Output directory must be empty; no overwrite or implicit resume')
    directory.mkdir(parents=True,exist_ok=True)
    journal=directory/'runs.jsonl'
    config={'schema':'virgo-rng-restart-acquisition-v1','created_utc':_now(),
            'setup':setup,'runs_requested':runs,'samples_per_run':samples,
            'rate':rate,'freq':freq,'gain':gain,'device':device,
            'rtl_binary':binary,'rtl_sha256':sha256(binary),
            'reset_mode':'manual-operator-attested' if manual else 'external-command-unverified',
            'restart_command':restart_command,
            'warning':'A fresh rtl_sdr process is not a proven physical restart. Verify USB power cycling, tuning and first-sample behavior; no automatic NIST compliance.'}
    (directory/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    completed=0
    for index in range(runs):
        if manual:
            answer=input(f'Run {index+1}/{runs}: physically power-cycle SDR, reconnect, then type RESET: ')
            if answer != 'RESET':
                raise RuntimeError('Operator did not confirm physical reset')
        else:
            command=shlex.split(restart_command)
            if not command: raise ValueError('Empty reset command')
            subprocess.run(command,check=True,timeout=timeout)
        output=directory/f'run_{index:04d}.cu8'
        command=[binary,'-d',str(device),'-f',str(freq),'-s',str(rate),'-g',str(gain),'-n',str(samples),str(output)]
        started=_now()
        result=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
        expected=2*samples
        actual=output.stat().st_size if output.exists() else 0
        record={'run':index,'started_utc':started,'ended_utc':_now(),
                'file':output.name,'bytes':actual,'expected_bytes':expected,
                'sha256':sha256(output) if actual else None,'returncode':result.returncode,
                'stderr_tail':result.stderr[-1000:], 'ok':result.returncode==0 and actual==expected}
        with journal.open('a') as stream:
            stream.write(json.dumps(record)+'\n');stream.flush()
        if not record['ok']:
            raise RuntimeError(f'Capture failed at run {index}: {actual}/{expected} bytes, returncode {result.returncode}; see runs.jsonl')
        completed+=1
    return {'completed':completed,'directory':str(directory)}


def pack(directory):
    directory=Path(directory)
    config=json.loads((directory/'config.json').read_text())
    records=[json.loads(line) for line in (directory/'runs.jsonl').read_text().splitlines() if line.strip()]
    runs=config['runs_requested']; samples=config['samples_per_run']
    if len(records)!=runs or any(r['run']!=i for i,r in enumerate(records)):
        raise ValueError('Incomplete, duplicated or unordered runs')
    outputs={'i':directory/'restart_i.bin','q':directory/'restart_q.bin'}
    # Verify ALL inputs before writing outputs.
    for record in records:
        file=directory/record['file']
        if not record['ok'] or not file.is_file() or file.stat().st_size!=samples*2 or sha256(file)!=record['sha256']:
            raise ValueError(f'Invalid capture: {file}')
    for output in outputs.values():
        if output.exists(): raise FileExistsError(output)
    with outputs['i'].open('wb') as fi,outputs['q'].open('wb') as fq:
        for record in records:
            data=(directory/record['file']).read_bytes()
            fi.write(data[::2]); fq.write(data[1::2])
    manifest={'schema':'virgo-rng-restart-matrix-v1','runs':runs,'samples_per_run':samples,
              'layout':'row-major: run 0 first 1000 samples, then run 1, etc.',
              'source_config_sha256':sha256(directory/'config.json'),
              'outputs':{key:{'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':sha256(path)} for key,path in outputs.items()},
              'warning':'Matrix construction is NOT NIST restart test. External ea_restart and physical restart evidence required.'}
    (directory/'restart_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
