"""Experimental SHA-256 conditioning. NOT a validated randomness extractor."""
import hashlib
from pathlib import Path

def condition_file(source, destination, block_bytes=4096):
    source=Path(source); destination=Path(destination)
    if source.resolve()==destination.resolve():
        raise ValueError('Input and output must differ')
    if block_bytes < 512 or block_bytes%2:
        raise ValueError('block_bytes must be even and at least 512')
    if source.stat().st_size < block_bytes:
        raise ValueError('Not enough input for one complete block')
    destination.parent.mkdir(parents=True,exist_ok=True)
    blocks=0
    with source.open('rb') as inp, destination.open('wb') as out:
        while len(chunk:=inp.read(block_bytes))==block_bytes:
            # Domain separation and index prevent ambiguous block encodings.
            out.write(hashlib.sha256(b'Virgo-RNG-v0.2-EXPERIMENTAL\x00'+blocks.to_bytes(8,'big')+chunk).digest())
            blocks+=1
    return {'blocks':blocks,'input_bytes_consumed':blocks*block_bytes,
            'output_bytes':blocks*32,'discarded_tail_bytes':source.stat().st_size-blocks*block_bytes,
            'status':'UNVALIDATED experimental SHA-256 conditioning; NOT for cryptographic use'}
