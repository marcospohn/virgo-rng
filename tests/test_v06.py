import io
import json
import numpy as np
import pytest
from virgo_rng.generator import generate, generate_file, SourceAlarm


def test_valid_stream(tmp_path):
    rng = np.random.default_rng(123)
    raw = rng.integers(30, 220, size=8192, dtype=np.uint8).tobytes()
    out, report = tmp_path/'bits.bin', tmp_path/'report.json'
    result = generate(io.BytesIO(raw), out, report, total_bytes=len(raw))
    assert out.stat().st_size == 64
    assert result['status'] == 'COMPLETED_UNVALIDATED'
    assert json.loads(report.read_text())['blocks_passed'] == 2


def test_constant_source_fails_closed(tmp_path):
    out, report = tmp_path/'bits.bin', tmp_path/'report.json'
    with pytest.raises(SourceAlarm):
        generate(io.BytesIO(bytes([128])*8192), out, report, total_bytes=8192)
    assert not out.exists()
    assert json.loads(report.read_text())['status'] == 'FAILED'


def test_late_failure_removes_output(tmp_path):
    rng = np.random.default_rng(123)
    good = rng.integers(30, 220, size=4096, dtype=np.uint8).tobytes()
    out, report = tmp_path/'bits.bin', tmp_path/'report.json'
    with pytest.raises(SourceAlarm):
        generate(io.BytesIO(good + bytes([127])*4096), out, report, total_bytes=8192)
    assert not out.exists()
    assert json.loads(report.read_text())['blocks_passed'] == 1


def test_short_read(tmp_path):
    out, report = tmp_path/'bits.bin', tmp_path/'report.json'
    with pytest.raises(SourceAlarm):
        generate(io.BytesIO(b'abc'), out, report, total_bytes=4096)
    assert not out.exists()


def test_same_source_output_rejected(tmp_path):
    p = tmp_path/'source.cu8'
    p.write_bytes(bytes(4096))
    with pytest.raises(ValueError):
        generate_file(p, p, tmp_path/'r.json')


def test_startup_anomaly_rejected(tmp_path):
    rng = np.random.default_rng(4)
    bad = bytes([127])*700 + rng.integers(30,220,size=3396,dtype=np.uint8).tobytes()
    out, report = tmp_path/'bits.bin', tmp_path/'report.json'
    with pytest.raises(SourceAlarm):
        generate(io.BytesIO(bad), out, report, total_bytes=4096)
    assert not out.exists()
