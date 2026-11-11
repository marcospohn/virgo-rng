import json
from pathlib import Path
from virgo_rng.nist90b import sha256
from virgo_rng.restart15 import audit
from virgo_rng.restart14 import evaluate


def trial(tmp_path):
    folder=tmp_path/'trial';folder.mkdir()
    (folder/'config.json').write_text(json.dumps({'runs_requested':2,'samples_per_run':3,'reset_mode':'manual-operator-attested'}))
    records=[]
    for i in range(2):
        f=folder/f'run_{i:04d}.cu8';f.write_bytes(bytes([i,4,5,6,7,8]))
        records.append({'run':i,'file':f.name,'bytes':6,'sha256':sha256(f),'ok':True,'returncode':0})
    (folder/'runs.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records))
    return folder


def test_audit_trial(tmp_path):
    folder=trial(tmp_path)
    assert audit(folder)['integrity_ok']
    assert not audit(folder)['physical_restart_verified']
    assert not audit(folder,require_full=True)['integrity_ok']


def test_audit_corruption(tmp_path):
    folder=trial(tmp_path)
    (folder/'run_0001.cu8').write_bytes(b'corrupt')
    assert not audit(folder)['integrity_ok']


def test_audit_pack(tmp_path):
    from virgo_rng.restart13 import pack
    folder=trial(tmp_path)
    pack(folder)
    assert audit(folder)['integrity_ok']
    (folder/'restart_q.bin').write_bytes(b'bad')
    assert not audit(folder)['integrity_ok']


def test_restart_evaluate_both_entropies(tmp_path):
    folder=tmp_path/'full';folder.mkdir()
    cfg={'runs_requested':1000,'samples_per_run':1000,'reset_mode':'manual-operator-attested'}
    (folder/'config.json').write_text(json.dumps(cfg))
    records=[]
    for i in range(1000):
        f=folder/f'run_{i:04d}.cu8';f.write_bytes(bytes([i%256, (i+1)%256])*1000)
        records.append({'run':i,'file':f.name,'bytes':2000,'sha256':sha256(f),'ok':True,'returncode':0})
    (folder/'runs.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records))
    from virgo_rng.restart13 import pack
    pack(folder)
    bin_dir=tmp_path/'bin';bin_dir.mkdir()
    exe=bin_dir/'ea_restart'
    exe.write_text('#!/bin/sh\necho "fake test only: $*"\n')
    exe.chmod(0o755)
    reports=evaluate(folder,binary=str(exe),h_i=4.0,h_q=3.5,ack_physical_restarts=True)
    ri=json.loads(Path(reports['i']).read_text());rq=json.loads(Path(reports['q']).read_text())
    assert ri['h_i']==4.0 and rq['h_i']==3.5
    assert ri['command'][-1]=='4' and rq['command'][-1]=='3.5'
