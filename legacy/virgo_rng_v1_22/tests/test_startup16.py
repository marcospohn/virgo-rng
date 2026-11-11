import json
import os
from pathlib import Path
import numpy as np
import pytest
from virgo_rng.startup16 import analyze_capture, analyze_campaign, collect


def test_analyze_synthetic(tmp_path):
    p=tmp_path/'sample.cu8'
    a=np.arange(128,dtype=np.uint8)
    p.write_bytes(np.column_stack((a,255-a)).tobytes())
    r=analyze_capture(p,block_pairs=16,max_blocks=4)
    assert r['blocks_analyzed']==4
    assert len(r['channels']['i']['blocks'])==4
    assert r['channels']['q']['blocks'][0]['unique_symbols']==16
    assert r['channels']['i']['blocks'][0]['shannon_bits']==pytest.approx(4)


def test_bad_file(tmp_path):
    p=tmp_path/'bad.cu8';p.write_bytes(b'abc')
    with pytest.raises(ValueError): analyze_capture(p,block_pairs=2)


def test_collect_fake_rtl_and_reanalyze(tmp_path,monkeypatch):
    binary=tmp_path/'rtl_sdr'
    binary.write_text('''#!/usr/bin/env python3
import sys
from pathlib import Path
n=int(sys.argv[sys.argv.index('-n')+1])
sys.stdout.buffer.write(bytes([128,127]) * n)
print('[R82XX] PLL not locked!',file=sys.stderr)
''')
    binary.chmod(0o755)
    monkeypatch.setattr('builtins.input',lambda _: 'RESET')
    directory=tmp_path/'trial'
    report=collect(directory,runs=2,pairs=32,block_pairs=8,rtl_binary=str(binary),plot=False)
    assert report['pll_warning_runs']==2
    assert report['runs_analyzed']==2
    assert analyze_campaign(directory,plot=False)['runs_analyzed']==2
    (directory/'startup_0000.cu8').write_bytes(b'\0'*64)
    with pytest.raises(ValueError,match='Integrity'): analyze_campaign(directory,plot=False)


def test_refuses_overwrite(tmp_path,monkeypatch):
    d=tmp_path/'existing';d.mkdir();(d/'file').write_text('x')
    with pytest.raises(FileExistsError): collect(d,runs=1,pairs=16,block_pairs=8,rtl_binary='python3',plot=False)


def test_bounded_capture_overproducing_rtl(tmp_path, monkeypatch):
    binary=tmp_path/'rtl_sdr_overproducing'
    binary.write_text('''#!/usr/bin/env python3
import sys
while True:
    sys.stdout.buffer.write(bytes([128,127]) * 4096)
    sys.stdout.buffer.flush()
''')
    binary.chmod(0o755)
    monkeypatch.setattr('builtins.input',lambda _: 'RESET')
    directory=tmp_path/'bounded'
    report=collect(directory,runs=1,pairs=32,block_pairs=8,rtl_binary=str(binary),plot=False,timeout=5)
    assert report['runs_analyzed']==1
    assert (directory/'startup_0000.cu8').stat().st_size == 64
    record=json.loads((directory/'runs.jsonl').read_text().strip())
    assert record['capture_status']=='bounded-complete'
