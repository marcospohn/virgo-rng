import json
import pytest
from virgo_rng.nist_screen113 import prepare, evaluate


def test_prepare(tmp_path):
    source=tmp_path/'capture.cu8'
    source.write_bytes(bytes([120,130])*3_000_000)
    out=tmp_path/'out'
    manifest=prepare(source,out)
    assert len(manifest['entries'])==6
    assert (out/'beginning_i.bin').stat().st_size==1_000_000
    assert (out/'end_q.bin').read_bytes()[:2]==bytes([130,130])
    with pytest.raises(FileExistsError):
        prepare(source,out)
    assert json.loads((out/'manifest.json').read_text())['source_sha256']


def test_invalid(tmp_path):
    src=tmp_path/'bad.cu8';src.write_bytes(b'123')
    with pytest.raises(ValueError):prepare(src,tmp_path/'out')
