"""Exploratory first-delivered-IQ startup characterization, NOT ADC startup or NIST validation."""
import hashlib
import json
import math
import os
import select
import tempfile
import time
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _stats(values):
    x = np.asarray(values, dtype=np.float64)
    if not len(x):
        raise ValueError('Empty analysis window')
    counts = np.bincount(x.astype(np.uint8), minlength=256)
    p = counts[counts > 0] / len(x)
    variance = float(np.var(x))
    centered = x - np.mean(x)
    lag1 = float(np.dot(centered[:-1], centered[1:]) / np.dot(centered, centered)) if len(x) > 1 and variance > 0 else None
    return {'mean': float(np.mean(x)), 'std': float(np.std(x)),
            'shannon_bits': float(-np.sum(p * np.log2(p))),
            'most_common_probability': float(np.max(p)), 'unique_symbols': int(np.count_nonzero(counts)),
            'lag1_autocorrelation': lag1}


def analyze_capture(path, *, block_pairs=4096, max_blocks=None):
    path = Path(path)
    raw = path.read_bytes()
    if len(raw) % 2:
        raise ValueError('CU8 must contain complete I/Q pairs')
    pairs = len(raw) // 2
    if block_pairs < 2 or (max_blocks is not None and max_blocks < 2) or pairs < block_pairs * 2:
        raise ValueError('At least two complete blocks are required')
    data = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 2)
    n = pairs // block_pairs if max_blocks is None else min(pairs // block_pairs, max_blocks)
    channels = {}
    for channel, index in (('i', 0), ('q', 1)):
        blocks = [_stats(data[k * block_pairs:(k + 1) * block_pairs, index]) for k in range(n)]
        early, late = blocks[0], blocks[-1]
        channels[channel] = {'blocks': blocks,
                             'first_vs_rest': {field: (float(blocks[0][field] - np.mean([b[field] for b in blocks[1:]])) if blocks[0][field] is not None and all(b[field] is not None for b in blocks[1:]) else None) for field in ('mean', 'std', 'shannon_bits', 'lag1_autocorrelation')},
                             'first_vs_last': {'mean_delta': early['mean'] - late['mean'],
                                               'std_ratio': early['std'] / late['std'] if late['std'] else None,
                                               'shannon_delta_bits': early['shannon_bits'] - late['shannon_bits']}}
    return {'file': path.name, 'bytes': len(raw), 'sha256': _sha(path),
            'pairs': pairs, 'block_pairs': block_pairs, 'blocks_analyzed': n,
            'channels': channels}


def _plot(report, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    for channel in ('i', 'q'):
        blocks = report['channels'][channel]['blocks']
        for ax, field, title in zip(axes, ('mean', 'std', 'shannon_bits'),
                                    ('Mean byte value', 'Standard deviation', 'Empirical Shannon entropy (bits)')):
            ax.plot(range(1, len(blocks) + 1), [b[field] for b in blocks], marker='.', label=channel.upper())
            ax.set_ylabel(title)
    axes[0].legend()
    axes[-1].set_xlabel('Block index (first samples delivered by rtl_sdr)')
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _bounded_capture(cmd, output, expected_bytes, timeout):
    """Read exactly the requested bytes from rtl_sdr stdout, then stop it.

    This does not depend on rtl_sdr honoring -n; stdout '-' must be supported.
    """
    deadline = time.monotonic() + timeout
    received = 0
    with tempfile.TemporaryFile(mode='w+b') as errors:
        proc = subprocess.Popen(cmd[:-1] + ['-'], stdout=subprocess.PIPE, stderr=errors)
        try:
            with Path(output).open('wb') as sink:
                while received < expected_bytes:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Timed out before receiving requested IQ bytes')
                    readable, _, _ = select.select([proc.stdout], [], [], remaining)
                    if not readable:
                        raise TimeoutError('Timed out waiting for RTL-SDR output')
                    chunk = os.read(proc.stdout.fileno(), min(65536, expected_bytes - received))
                    if not chunk:
                        break
                    sink.write(chunk)
                    received += len(chunk)
        except TimeoutError:
            status = 'timeout'
        else:
            status = 'bounded-complete' if received == expected_bytes else 'early-eof'
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                rc = proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                rc = proc.wait()
            proc.stdout.close()
        errors.seek(0)
        stderr = errors.read().decode('utf-8', errors='replace')
    return stderr, rc, status, received


def collect(directory, *, runs=3, pairs=262144, block_pairs=4096, rate=2400000,
            freq=1420405752, gain=30, device=0, rtl_binary='rtl_sdr',
            manual=True, setup='unknown', timeout=40, plot=True):
    if runs < 1 or pairs < 2 * block_pairs or block_pairs < 2 or rate <= 0 or freq <= 0 or timeout <= 0:
        raise ValueError('Invalid capture parameters')
    if not manual:
        raise ValueError('This release requires explicit operator-attested physical power cycles')
    binary = shutil.which(rtl_binary)
    if not binary:
        raise FileNotFoundError(f'Executable not found: {rtl_binary}')
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError('Directory must be empty; previous measurements are never overwritten')
    directory.mkdir(parents=True, exist_ok=True)
    config = {'schema': 'virgo-rng-startup-v1', 'created_utc': _utc(), 'runs': runs,
              'pairs_per_run': pairs, 'block_pairs': block_pairs, 'rate': rate,
              'freq': freq, 'gain_requested': gain, 'device': device, 'setup': setup,
              'rtl_binary': str(Path(binary).resolve()), 'rtl_binary_sha256': _sha(binary),
              'physical_restart_evidence': 'operator-attested-only',
              'limitation': 'Driver initialization may discard samples; these are first delivered samples, not guaranteed first ADC samples.'}
    (directory / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    for idx in range(runs):
        answer = input(f'Run {idx+1}/{runs}: physically disconnect USB power, wait >=5 seconds, reconnect, then type RESET: ')
        if answer != 'RESET':
            raise RuntimeError('Operator did not attest physical reset')
        output = directory / f'startup_{idx:04d}.cu8'
        cmd = [binary, '-d', str(device), '-f', str(freq), '-s', str(rate), '-g', str(gain),
               '-n', str(pairs), str(output)]
        started = _utc()
        stderr, rc, capture_status, received = _bounded_capture(cmd, output, pairs * 2, timeout)
        size = output.stat().st_size if output.exists() else 0
        record = {'run': idx, 'started_utc': started, 'ended_utc': _utc(), 'file': output.name,
                  'bytes': size, 'sha256': _sha(output) if size else None,
                  'returncode': rc, 'capture_status': capture_status, 'bytes_received': received, 'pll_not_locked': bool(re.search(r'PLL\s+not\s+locked', stderr, re.I)),
                  'stderr': stderr[-5000:], 'ok': capture_status == 'bounded-complete' and size == pairs * 2}
        with (directory / 'runs.jsonl').open('a') as f:
            f.write(json.dumps(record) + '\n')
        if not record['ok']:
            raise RuntimeError(f'Capture {idx+1} failed; see runs.jsonl ({size}/{pairs*2} bytes, status={capture_status}, rc={rc})')
    return analyze_campaign(directory, block_pairs=block_pairs, plot=plot)


def analyze_campaign(directory, *, block_pairs=None, plot=True):
    directory = Path(directory)
    config = json.loads((directory / 'config.json').read_text())
    if config.get('schema') != 'virgo-rng-startup-v1':
        raise ValueError('Not a startup16 campaign')
    records = [json.loads(line) for line in (directory / 'runs.jsonl').read_text().splitlines() if line.strip()]
    if len(records) != config['runs'] or any(r['run'] != i for i, r in enumerate(records)):
        raise ValueError('Incomplete or unordered campaign')
    if block_pairs is None:
        block_pairs = config['block_pairs']
    analyses = []
    for record in records:
        file = directory / record['file']
        if (not record['ok'] or not file.is_file() or file.stat().st_size != record['bytes']
                or _sha(file) != record['sha256']):
            raise ValueError(f'Integrity failure for {file}')
        analysis = analyze_capture(file, block_pairs=block_pairs)
        analysis['run'] = record['run']
        analysis['pll_not_locked'] = record['pll_not_locked']
        analyses.append(analysis)
    report = {'schema': 'virgo-rng-startup-analysis-v1', 'config': config,
              'runs_analyzed': len(analyses),
              'pll_warning_runs': sum(r['pll_not_locked'] for r in analyses),
              'coverage': {'blocks_per_capture': [a['blocks_analyzed'] for a in analyses], 'all_complete_blocks_analyzed': all(a['blocks_analyzed'] == a['pairs']//a['block_pairs'] for a in analyses)},
              'comparison': {ch: {'first_minus_rest_shannon_by_run': [a['channels'][ch]['first_vs_rest']['shannon_bits'] for a in analyses], 'positive_count': sum(a['channels'][ch]['first_vs_rest']['shannon_bits'] > 0 for a in analyses)} for ch in ('i','q')},
              'analyses': analyses,
              'cautions': ['Empirical Shannon entropy is NOT a min-entropy lower bound.',
                           'No proof of USB power cycling beyond operator attestation.',
                           'First rtl_sdr samples may follow hardware/driver warm-up or dropped samples.',
                           'PLL warning in stderr is not proof of persistent PLL failure.',
                           'No NIST restart compliance or cryptographic entropy claim.']}
    (directory / 'startup_report.json').write_text(json.dumps(report, indent=2) + '\n')
    if plot:
        for analysis in analyses:
            _plot(analysis, directory / f"startup_{analysis['run']:04d}.png")
    return report
