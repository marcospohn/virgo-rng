"""Bounded-memory RTL-SDR streaming acquisition with diagnostic windows."""
import json
import subprocess
import shutil
from pathlib import Path
import numpy as np


def summarize_chunk(data: bytes, index: int) -> dict:
    a = np.frombuffer(data, dtype=np.uint8)
    if len(a) < 512 or len(a) % 2:
        raise ValueError("Need >=512 even bytes of interleaved I/Q")
    counts = np.bincount(a, minlength=256)
    pmax = counts.max() / len(a)
    i = a[::2].astype(np.float64) - 127.5
    q = a[1::2].astype(np.float64) - 127.5
    def lag1(v):
        v -= v.mean()
        denom = np.dot(v, v)
        return float(np.dot(v[:-1], v[1:]) / denom) if denom else 0.0
    return {"index": index, "bytes": len(data),
            "mean_i": float(i.mean()), "mean_q": float(q.mean()),
            "std_i": float(i.std()), "std_q": float(q.std()),
            "clipped_fraction": float(np.mean((a == 0) | (a == 255))),
            "marginal_min_entropy_bits_per_byte_unvalidated": float(-np.log2(pmax)),
            "acf1_i": lag1(i), "acf1_q": lag1(q)}


def process_stream(reader, output, report, *, total_bytes, chunk_bytes=262144, setup="unknown", metadata=None):
    if total_bytes < 512 or total_bytes % 2 or chunk_bytes < 512 or chunk_bytes % 2:
        raise ValueError("Byte counts must be even and >=512")
    output, report = Path(output), Path(report)
    if output.resolve() == report.resolve():
        raise ValueError("Data and report paths must differ")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    windows = []
    remaining = total_bytes
    with output.open("wb") as out:
        while remaining:
            expected = min(chunk_bytes, remaining)
            pieces = []
            received = 0
            while received < expected:
                part = reader.read(expected - received)
                if not part:
                    raise EOFError(f"Short acquisition: {received}/{expected} bytes in current chunk")
                pieces.append(part)
                received += len(part)
            data = b"".join(pieces)
            out.write(data)
            windows.append(summarize_chunk(data, len(windows)))
            remaining -= expected
    result = {"setup": setup, "bytes_captured": total_bytes, "windows": windows,
              "metadata": metadata or {},
              "security_status": "UNVALIDATED diagnostic statistics; NOT cryptographically secure"}
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def capture_stream(output, report, *, seconds, rate, freq, gain, setup, chunk_bytes=262144):
    if not (0 < seconds <= 3600) or not (225001 <= rate <= 3200000) or freq <= 0:
        raise ValueError("Invalid capture settings")
    if shutil.which("rtl_sdr") is None:
        raise RuntimeError("rtl_sdr executable not found; install rtl-sdr")
    total = int(seconds * rate) * 2
    if total < 512:
        raise ValueError("Capture too short")
    # -n counts complex I/Q samples, - outputs raw interleaved unsigned bytes.
    command = ["rtl_sdr", "-f", str(freq), "-s", str(rate), "-n", str(total // 2)]
    if gain is not None:
        command += ["-g", str(gain)]
    command += ["-"]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
        try:
            result = process_stream(proc.stdout, output, report, total_bytes=total,
                                    chunk_bytes=chunk_bytes, setup=setup,
                                    metadata={"frequency_hz": freq, "sample_rate_sps": rate,
                                              "gain_db": gain, "requested_seconds": seconds,
                                              "backend": "rtl_sdr"})
            code = proc.wait(timeout=30)
            if code != 0:
                raise RuntimeError(f"rtl_sdr exited with status {code}")
            return result
        except BaseException:
            proc.kill()
            proc.wait()
            raise
