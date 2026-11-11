"""Experimental SDR entropy acquisition and diagnostics; not a certified RNG."""
import hashlib
import json
from pathlib import Path
import numpy as np


def analyze(raw: bytes, max_lag: int = 16) -> dict:
    a = np.frombuffer(raw, dtype=np.uint8)
    if len(a) < 512 or len(a) % 2:
        raise ValueError('Input must contain at least 256 complete IQ samples')
    i, q = a[::2].astype(np.float64) - 127.5, a[1::2].astype(np.float64) - 127.5
    counts = np.bincount(a, minlength=256)
    probabilities = counts[counts > 0] / len(a)
    # Marginal plug-in statistic, NOT a validated entropy-rate bound.
    marginal_min = float(-np.log2(probabilities.max()))
    def acf(v):
        v = v - v.mean()
        denom = np.dot(v, v)
        return [float(np.dot(v[:-lag], v[lag:]) / denom) if denom else 0.0 for lag in range(1, min(max_lag, len(v)-1)+1)]
    return {
        'samples_iq': len(i), 'mean_i': float(i.mean()), 'mean_q': float(q.mean()),
        'std_i': float(i.std()), 'std_q': float(q.std()),
        'clipped_fraction': float(np.mean((a == 0) | (a == 255))),
        'marginal_min_entropy_bits_per_byte_unvalidated': marginal_min,
        'acf_i': acf(i), 'acf_q': acf(q),
        'sha256_raw': hashlib.sha256(raw).hexdigest(),
        'security_status': 'UNVALIDATED: no certified entropy estimate; do not use for cryptography',
    }


def acquire(seconds: float, sample_rate: int, center_frequency: int, gain: float | None) -> bytes:
    try:
        from rtlsdr import RtlSdr
    except ImportError as exc:
        raise RuntimeError('Install optional hardware dependencies: pip install -e ".[sdr]"') from exc
    sdr = RtlSdr()
    try:
        sdr.sample_rate = sample_rate
        sdr.center_freq = center_frequency
        sdr.gain = 'auto' if gain is None else gain
        # read_bytes returns interleaved unsigned I/Q bytes; chunk to limit read size.
        remaining = int(seconds * sample_rate)
        if remaining < 256:
            raise ValueError('Duration too short')
        out = bytearray()
        while remaining:
            n = min(remaining, 262144)
            chunk = sdr.read_bytes(2*n)
            if len(chunk) != 2*n:
                raise RuntimeError(f'Short read: expected {2*n}, received {len(chunk)}')
            out.extend(chunk)
            remaining -= n
        return bytes(out)
    finally:
        sdr.close()


def save_report(path: Path, report: dict):
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
