import io
import json
import numpy as np
import pytest
from virgo_rng.stream import process_stream, summarize_chunk


def test_summary_constant():
    a = bytes([127, 128]) * 512
    d = summarize_chunk(a, 0)
    assert d['acf1_i'] == 0
    assert d['marginal_min_entropy_bits_per_byte_unvalidated'] == pytest.approx(1)


def test_stream_file(tmp_path):
    data = np.random.default_rng(9).integers(0, 256, 8192, dtype=np.uint8).tobytes()
    output, report = tmp_path/'out.cu8', tmp_path/'report.json'
    process_stream(io.BytesIO(data), output, report, total_bytes=len(data), chunk_bytes=1024, setup='indoor-dipole')
    assert output.read_bytes() == data
    assert len(json.loads(report.read_text())['windows']) == 8


def test_short_read(tmp_path):
    with pytest.raises(EOFError):
        process_stream(io.BytesIO(b'\0'*512),tmp_path/'x',tmp_path/'y',total_bytes=1024)


def test_bad_chunk(tmp_path):
    with pytest.raises(ValueError):
        process_stream(io.BytesIO(b'\0'*1024),tmp_path/'x',tmp_path/'y',total_bytes=1024,chunk_bytes=513)
