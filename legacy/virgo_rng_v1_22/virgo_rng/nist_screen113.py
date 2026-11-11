"""Non-IID reference-tool screening of separated raw SDR I and Q segments.

This is not an SP 800-90B validation, certification, or min-entropy guarantee.
"""
import json
from pathlib import Path
from .nist90b import sha256, run_nist
from .nist_campaign import parse_estimates


def prepare(source, output, *, pairs=1_000_000, setup='unknown'):
    source, output = Path(source), Path(output)
    if not source.is_file() or source.stat().st_size % 2:
        raise ValueError('Source must be an existing even-length CU8 file')
    total = source.stat().st_size // 2
    if pairs < 1_000_000 or total < 3 * pairs:
        raise ValueError('Need at least 3 disjoint segments of >=1,000,000 I/Q pairs')
    if output.resolve() == source.resolve():
        raise ValueError('Output cannot be input file')
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Output directory must be empty to prevent overwriting results')
    output.mkdir(parents=True, exist_ok=True)
    offsets = [('beginning', 0), ('middle', (total-pairs)//2), ('end', total-pairs)]
    entries = []
    with source.open('rb') as f:
        for label, offset in offsets:
            f.seek(2 * offset)
            data = f.read(2 * pairs)
            if len(data) != 2 * pairs:
                raise IOError('Truncated input')
            for channel, values in [('i', data[::2]), ('q', data[1::2])]:
                p = output / f'{label}_{channel}.bin'
                p.write_bytes(values)
                entries.append({'id':f'{label}_{channel}', 'path':str(p.resolve()),
                                'sha256':sha256(p), 'pairs':pairs, 'offset_pairs':offset,
                                'channel':channel})
    manifest = {'schema':'virgo-rng-nist-screen-v1', 'source':str(source.resolve()),
                'source_sha256':sha256(source), 'source_bytes':source.stat().st_size,
                'setup':setup, 'entries':entries,
                'note':'Within-recording non-IID screening; 6 disjoint-channel raw byte files; no conditioning or discarded startup samples; no physical restarts'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def evaluate(directory, *, binary, timeout=3600):
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_text())
    if manifest.get('schema') != 'virgo-rng-nist-screen-v1':
        raise ValueError('Unexpected manifest schema')
    rows = []
    for entry in manifest['entries']:
        p = Path(entry['path'])
        if not p.is_file() or sha256(p) != entry['sha256']:
            raise ValueError(f'Input missing or changed: {p}')
        report = directory / (entry['id'] + '_non_iid.json')
        try:
            result = run_nist(p, report, binary=binary, timeout=timeout)
            status = result['status']
            estimates = parse_estimates(result['stdout'])
        except (RuntimeError, FileNotFoundError, ValueError) as exc:
            status, estimates = 'failed', None
            rows.append({'id':entry['id'],'status':status,'error':str(exc), 'report':str(report)})
            continue
        rows.append({'id':entry['id'], 'status':status, 'estimates':estimates,
                     'report':str(report)})
    summary = {'schema':'virgo-rng-nist-screen-summary-v1','source_sha256':manifest['source_sha256'],
               'results':rows,'all_completed':all(r['status']=='completed' for r in rows),
               'limitations':['Not an SP 800-90B source validation, IID determination, or restart experiment',
                              'These are separate within-recording estimates, not an extraction rate',
                              'Do not sum I and Q estimates or infer independence',
                              'No characterization of environmental RF or adversarial influence',
                              'Official -t flag truncates bitstring assessment to 1M bits']}
    (directory/'screen_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary
