"""Diagnostic health tests, inspired by SP 800-90B, NOT a compliant implementation."""
from pathlib import Path
import numpy as np

def health_file(path, window_bytes=65536, repetition_cutoff=32, proportion_cutoff=0.10):
    if window_bytes < 256 or repetition_cutoff < 2 or not (0 < proportion_cutoff <= 1):
        raise ValueError('Invalid health parameters')
    total=0; max_run=0; run=0; previous=None; repeat_events=0; proportion_events=0
    windows=0; max_frequency=0.0; stats=[]
    with Path(path).open('rb') as f:
        while data:=f.read(window_bytes):
            a=np.frombuffer(data,dtype=np.uint8)
            if not len(a):break
            total+=len(a)
            counts=np.bincount(a,minlength=256)
            freq=float(counts.max()/len(a)); max_frequency=max(max_frequency,freq)
            windows+=1
            if freq>proportion_cutoff: proportion_events+=1
            # Includes run crossing file-chunk boundaries
            for value in a:
                v=int(value)
                if v==previous:run+=1
                else:run=1;previous=v
                max_run=max(max_run,run)
                if run==repetition_cutoff:repeat_events+=1
            stats.append({'index':windows-1,'bytes':len(a),'max_symbol_frequency':freq,
                          'mean':float(a.mean()),'std':float(a.std())})
    if total==0:raise ValueError('Empty file')
    return {'input_bytes':total,'windows':windows,'window_bytes':window_bytes,
            'repetition_cutoff':repetition_cutoff,'max_identical_run':max_run,
            'repetition_alarm_count':repeat_events,'proportion_cutoff':proportion_cutoff,
            'max_window_symbol_frequency':max_frequency,'proportion_alarm_windows':proportion_events,
            'window_stats':stats,
            'status':'DIAGNOSTIC ONLY: heuristic thresholds, NOT NIST SP 800-90B RCT/APT conformance; no validated entropy bound'}
