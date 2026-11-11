"""Research-only streaming conditioner. No certified entropy claim."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import numpy as np

class SourceAlarm(RuntimeError):
    pass

class HealthMonitor:
    """Heuristic per-block checks; NOT SP 800-90B-compliant health tests."""
    def __init__(self, *, repeat_limit=32, proportion_limit=0.12, clipping_limit=0.01,
                 acf_limit=0.50):
        if repeat_limit < 2 or not 0 < proportion_limit <= 1 or not 0 <= clipping_limit <= 1 or not 0 < acf_limit <= 1:
            raise ValueError('Invalid heuristic thresholds')
        self.repeat_limit = repeat_limit
        self.proportion_limit = proportion_limit
        self.clipping_limit = clipping_limit
        self.acf_limit = acf_limit
        self.previous = None
        self.run = 0
        self.max_run = 0

    def check(self, data):
        a = np.frombuffer(data, dtype=np.uint8)
        if len(a) < 512 or len(a) % 2:
            raise SourceAlarm('Incomplete or misaligned I/Q block')
        counts = np.bincount(a, minlength=256)
        pmax = float(counts.max() / len(a))
        clipped = float(np.mean((a == 0) | (a == 255)))
        # Include repetitions spanning block boundaries.
        for v in a:
            value = int(v)
            self.run = self.run + 1 if value == self.previous else 1
            self.previous = value
            self.max_run = max(self.max_run, self.run)
            if self.run >= self.repeat_limit:
                raise SourceAlarm('Repeated symbol threshold exceeded')
        acfs = []
        for channel in (a[::2], a[1::2]):
            x = channel.astype(np.float64)
            x -= x.mean()
            den = float(np.dot(x, x))
            acfs.append(float(np.dot(x[:-1], x[1:]) / den) if den else 1.0)
        if pmax > self.proportion_limit:
            raise SourceAlarm('Symbol concentration threshold exceeded')
        if clipped > self.clipping_limit:
            raise SourceAlarm('Clipping threshold exceeded')
        if any(abs(v) > self.acf_limit for v in acfs):
            raise SourceAlarm('Lag-1 autocorrelation threshold exceeded')
        return {'max_symbol_fraction': pmax, 'clipped_fraction': clipped,
                'acf1_i': acfs[0], 'acf1_q': acfs[1]}


def _read_exact(reader, size):
    chunks = []
    total = 0
    while total < size:
        part = reader.read(size - total)
        if not part:
            break
        chunks.append(part)
        total += len(part)
    return b''.join(chunks)


def generate(reader, output, report, *, total_bytes, block_bytes=4096,
             setup='unknown', metadata=None, monitor=None):
    """Process a finite byte stream, emitting SHA256(block) only for healthy blocks.

    Any failure removes the partial output and records a failure report.
    SHA-256 output is unvalidated and MUST NOT be used for cryptography.
    """
    output, report = Path(output), Path(report)
    if output.resolve() == report.resolve():
        raise ValueError('Output and report must differ')
    if block_bytes < 512 or block_bytes % 2 or total_bytes < block_bytes or total_bytes % block_bytes:
        raise ValueError('total_bytes must be a positive multiple of even block_bytes >= 512')
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    monitor = monitor or HealthMonitor()
    summary = {'status': 'FAILED', 'security_status': 'UNVALIDATED; NEVER use for cryptography',
               'setup': setup, 'metadata': metadata or {}, 'input_bytes': 0,
               'output_bytes': 0, 'blocks_passed': 0, 'block_bytes': block_bytes,
               'heuristic_thresholds': {'repeat_limit': monitor.repeat_limit,
                  'proportion_limit': monitor.proportion_limit,
                  'clipping_limit': monitor.clipping_limit, 'acf_limit': monitor.acf_limit},
               'diagnostics': {'max_symbol_fraction': 0.0, 'max_clipped_fraction': 0.0,
                               'max_abs_acf1': 0.0}}
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=output.parent, prefix='.virgo-rng-',
                                         delete=False) as sink:
            temp_path = Path(sink.name)
            for _ in range(total_bytes // block_bytes):
                block = _read_exact(reader, block_bytes)
                if len(block) != block_bytes:
                    raise SourceAlarm('Short read / incomplete capture')
                stats = monitor.check(block)
                sink.write(hashlib.sha256(block).digest())
                summary['input_bytes'] += len(block)
                summary['output_bytes'] += 32
                summary['blocks_passed'] += 1
                diag = summary['diagnostics']
                diag['max_symbol_fraction'] = max(diag['max_symbol_fraction'], stats['max_symbol_fraction'])
                diag['max_clipped_fraction'] = max(diag['max_clipped_fraction'], stats['clipped_fraction'])
                diag['max_abs_acf1'] = max(diag['max_abs_acf1'], abs(stats['acf1_i']), abs(stats['acf1_q']))
        os.replace(temp_path, output)
        temp_path = None
        summary['status'] = 'COMPLETED_UNVALIDATED'
    except BaseException as exc:
        summary['failure_reason'] = str(exc)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        raise
    finally:
        report.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


def generate_file(source, output, report, **kwargs):
    source = Path(source)
    if source.resolve() in (Path(output).resolve(), Path(report).resolve()):
        raise ValueError('Input must differ from outputs')
    with source.open('rb') as f:
        return generate(f, output, report, total_bytes=source.stat().st_size,
                        metadata={'source_file': str(source)}, **kwargs)


def generate_live(output, report, *, seconds, rate, freq, gain=None, **kwargs):
    if not 0 < seconds <= 3600 or not 225001 <= rate <= 3200000 or freq <= 0:
        raise ValueError('Invalid acquisition settings')
    if shutil.which('rtl_sdr') is None:
        raise RuntimeError('rtl_sdr not found')
    block_bytes = kwargs.get('block_bytes', 4096)
    samples = int(seconds * rate)
    # Round down to full blocks, with matching rtl_sdr -n sample count.
    total_bytes = samples * 2 // block_bytes * block_bytes
    if total_bytes < block_bytes:
        raise ValueError('Capture too short')
    command = ['rtl_sdr', '-f', str(freq), '-s', str(rate), '-n', str(total_bytes // 2)]
    if gain is not None:
        command += ['-g', str(gain)]
    command += ['-']
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
        try:
            result = generate(proc.stdout, output, report, total_bytes=total_bytes,
                              metadata={'backend': 'rtl_sdr', 'frequency_hz': freq,
                                        'sample_rate_sps': rate, 'gain_db': gain}, **kwargs)
            if proc.wait(timeout=30) != 0:
                Path(output).unlink(missing_ok=True)
                result['status'] = 'FAILED'
                result['failure_reason'] = 'rtl_sdr exited unsuccessfully'
                Path(report).write_text(json.dumps(result, indent=2) + '\n')
                raise RuntimeError(result['failure_reason'])
            return result
        except BaseException:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            raise
