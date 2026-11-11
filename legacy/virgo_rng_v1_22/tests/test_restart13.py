import json
import stat
import pytest
from virgo_rng.restart13 import collect, pack

def test_collect_and_pack(tmp_path):
    fake=tmp_path/'fake_rtl'
    fake.write_text('#!/usr/bin/env python3\nimport sys\na=sys.argv\nn=int(a[a.index("-n")+1]);open(a[-1],"wb").write(bytes([12,34])*n)\n')
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    reset=tmp_path/'reset';reset.write_text('#!/bin/sh\nexit 0\n');reset.chmod(reset.stat().st_mode | stat.S_IXUSR)
    folder=tmp_path/'runs'
    collect(folder,runs=3,samples=5,rtl_binary=str(fake),restart_command=str(reset))
    manifest=pack(folder)
    assert (folder/'restart_i.bin').read_bytes()==bytes([12])*15
    assert (folder/'restart_q.bin').read_bytes()==bytes([34])*15
    assert manifest['runs']==3
    with pytest.raises(FileExistsError): pack(folder)

def test_requires_reset(tmp_path):
    with pytest.raises(ValueError):collect(tmp_path/'runs')

def test_incomplete(tmp_path):
    folder=tmp_path/'runs';folder.mkdir()
    (folder/'config.json').write_text(json.dumps({'runs_requested':2,'samples_per_run':1000}))
    (folder/'runs.jsonl').write_text('')
    with pytest.raises(ValueError):pack(folder)
