"""Reproducible bridge to external, unmodified NIST SP800-90B executables.
No entropy estimation is implemented here; no NIST certification is implied.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def prepare_cu8(source, output_dir, *, skip_pairs=0, max_pairs=None, setup="unknown"):
    """Demultiplex interleaved unsigned 8-bit I,Q into one-byte-per-symbol files."""
    source = Path(source)
    output_dir = Path(output_dir)
    if skip_pairs < 0 or max_pairs is not None and max_pairs <= 0:
        raise ValueError("skip_pairs must be nonnegative; max_pairs must be positive")
    if not source.is_file():
        raise FileNotFoundError(source)
    size = source.stat().st_size
    if size % 2:
        raise ValueError("CU8 input must have an even number of bytes")
    total_pairs = size // 2
    if skip_pairs >= total_pairs:
        raise ValueError("skip_pairs reaches beyond the recording")
    pairs = min(total_pairs - skip_pairs, max_pairs or total_pairs)
    if pairs < 1000000:
        raise ValueError("At least 1,000,000 samples per channel required for this assessment workflow")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {ch: output_dir / (ch + "_symbols.bin") for ch in ("i", "q")}
    if any(p.resolve() == source.resolve() for p in outputs.values()):
        raise ValueError("Input and output paths must differ")
    with source.open("rb") as reader, outputs["i"].open("wb") as iout, outputs["q"].open("wb") as qout:
        reader.seek(skip_pairs * 2)
        left = pairs
        while left:
            data = reader.read(min(left, 524288) * 2)
            if not data or len(data) % 2:
                raise IOError("Unexpected truncated input")
            iout.write(data[0::2]); qout.write(data[1::2])
            left -= len(data) // 2
    manifest = {
        "format": "virgo-rng-nist90b-input-v1", "source": str(source.resolve()),
        "source_sha256": sha256(source), "setup": setup,
        "source_format": "RTL-SDR CU8: interleaved unsigned 8-bit I,Q",
        "transformation": "I=bytes[0::2], Q=bytes[1::2]; no whitening, centering, or filtering",
        "skip_pairs": skip_pairs, "samples_per_channel": pairs,
        "bits_per_symbol": 8,
        "outputs": {ch: {"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size} for ch, path in outputs.items()},
        "limitations": ["Separate I/Q assessments do not justify summing their entropy", "No restart dataset is produced", "No IID claim or cryptographic validation"],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def run_nist(input_file, report, *, binary="ea_non_iid", bits_per_symbol=8, timeout=3600):
    """Run installed reference executable, preserving full stdout/stderr and provenance."""
    if Path(binary).name not in {"ea_non_iid", "ea_iid"}:
        raise ValueError("Only ea_non_iid and ea_iid are supported")
    if not 1 <= bits_per_symbol <= 8:
        raise ValueError("bits_per_symbol must be 1..8")
    executable = shutil.which(binary) if os.sep not in binary else str(Path(binary).resolve())
    if not executable or not Path(executable).is_file():
        raise FileNotFoundError(f"NIST executable not found: {binary}; build the official NIST repository first")
    input_file = Path(input_file).resolve()
    if not input_file.is_file() or input_file.stat().st_size < 1000000:
        raise ValueError("Input file must contain at least 1,000,000 byte-encoded symbols")
    report = Path(report)
    cmd = [executable, "-i", "-t", str(input_file), str(bits_per_symbol)]
    start = time.monotonic()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        outcome = {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        outcome = {"returncode": None, "stdout": (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""), "stderr": (exc.stderr or b"").decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""), "timed_out": True}
    payload = {"status": "completed" if outcome["returncode"] == 0 else "failed", "tool": Path(executable).name, "tool_sha256": sha256(executable), "command": cmd, "input_sha256": sha256(input_file), "input_bytes": input_file.stat().st_size, "elapsed_seconds": round(time.monotonic()-start, 3), "mode": "initial, non-conditioned (-i); bitstring truncated to 1M bits (-t)", "disclaimer": "Reference tool output is preserved verbatim. This is not an entropy-source validation or an IID claim.", **outcome}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2) + "\n")
    if payload["status"] != "completed":
        raise RuntimeError(f"NIST tool failed; see {report}")
    return payload
