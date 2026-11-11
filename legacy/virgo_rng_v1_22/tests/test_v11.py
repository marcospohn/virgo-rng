import json
from pathlib import Path
import pytest
from virgo_rng.nist90b import prepare_cu8, run_nist


def test_demux_and_manifest(tmp_path):
    source=tmp_path/'in.cu8'
    source.write_bytes(bytes([7, 9])*1000000)
    report=prepare_cu8(source,tmp_path/'out',setup='indoor-dipole')
    assert report['samples_per_channel']==1000000
    assert (tmp_path/'out/i_symbols.bin').read_bytes()[:4]==bytes([7])*4
    assert (tmp_path/'out/q_symbols.bin').read_bytes()[-4:]==bytes([9])*4
    assert json.loads((tmp_path/'out/manifest.json').read_text())['source_sha256']==report['source_sha256']


def test_skip(tmp_path):
    src=tmp_path/'in.cu8'; src.write_bytes(bytes([1,2])*1000001)
    r=prepare_cu8(src,tmp_path/'out',skip_pairs=1)
    assert r['skip_pairs']==1


def test_reject_odd(tmp_path):
    src=tmp_path/'odd.cu8';src.write_bytes(b'abc')
    with pytest.raises(ValueError): prepare_cu8(src,tmp_path/'out')


def test_reject_too_short(tmp_path):
    src=tmp_path/'short.cu8';src.write_bytes(bytes([1,2])*999999)
    with pytest.raises(ValueError): prepare_cu8(src,tmp_path/'out')


def test_reject_bad_binary(tmp_path):
    with pytest.raises(ValueError): run_nist(tmp_path/'none',tmp_path/'report',binary='echo')


def test_reference_mock(tmp_path):
    src=tmp_path/'symbols.bin';src.write_bytes(b'\x00'*1000000)
    exe=tmp_path/'ea_non_iid';exe.write_text('#!/bin/sh\necho "reference output"\n');exe.chmod(0o755)
    report=tmp_path/'run.json'
    result=run_nist(src,report,binary=str(exe))
    assert result['returncode']==0
    assert 'reference output' in json.loads(report.read_text())['stdout']
