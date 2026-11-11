"""Continuous RTL-SDR CU8 time-window analysis. Research only; no entropy certification."""
import json, os, select, subprocess, tempfile, time, hashlib, shutil
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from .startup16 import _stats

def analyze_file(path, *, rate=2400000, window_pairs=240000, output=None, plot=True):
    path=Path(path)
    if rate<=0 or window_pairs<2: raise ValueError('Invalid rate/window')
    size=path.stat().st_size
    if size%2: raise ValueError('Odd CU8 byte count')
    total=size//2
    if total<window_pairs: raise ValueError('Insufficient complete window')
    digest=hashlib.sha256(); windows=[]
    with path.open('rb') as f:
        k=0
        while True:
            raw=f.read(window_pairs*2)
            if len(raw)<window_pairs*2:
                digest.update(raw)
                break
            digest.update(raw)
            a=np.frombuffer(raw,dtype=np.uint8).reshape(-1,2)
            windows.append({'index':k,'start_seconds':k*window_pairs/rate,'end_seconds':(k+1)*window_pairs/rate,'i':_stats(a[:,0]),'q':_stats(a[:,1])})
            k+=1
    result={'schema':'virgo-rng-temporal-v1','source':str(path),'sha256':digest.hexdigest(),'total_pairs':total,'windows_analyzed':len(windows),'trailing_pairs_not_analyzed':total-len(windows)*window_pairs,'rate':rate,'window_pairs':window_pairs,'window_seconds':window_pairs/rate,'windows':windows,'limitation':'Shannon entropy is not min-entropy; samples are delivered by driver, not necessarily first ADC samples. No RF origin attribution.'}
    if output:
        out=Path(output);out.mkdir(parents=True,exist_ok=True)
        (out/'temporal_report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        if plot:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            fig,ax=plt.subplots(3,1,figsize=(11,9),sharex=True)
            for ch in ('i','q'):
                for axis,key,title in zip(ax,('shannon_bits','std','lag1_autocorrelation'),('Shannon entropy (bits)','Standard deviation','Lag-1 autocorrelation')):
                    axis.plot([w['end_seconds'] for w in windows],[w[ch][key] for w in windows],label=ch.upper())
                    axis.set_ylabel(title)
            ax[0].legend();ax[-1].set_xlabel('Seconds since first delivered sample');fig.tight_layout()
            fig.savefig(out/'temporal_plot.png',dpi=150);plt.close(fig)
    return result

def capture(out, *, seconds=180, rate=2400000, freq=1420405752, gain=30, device=0, window_seconds=1.0, setup='indoor-dipole', rtl_binary='rtl_sdr', timeout_extra=60, plot=True):
    if seconds<=0 or rate<=0 or freq<=0 or window_seconds<=0: raise ValueError('Invalid capture parameters')
    if not shutil.which(rtl_binary): raise FileNotFoundError(rtl_binary)
    out=Path(out)
    if out.exists(): raise FileExistsError(out)
    out.mkdir(parents=True)
    pairs=int(seconds*rate); expected=pairs*2
    cmd=[rtl_binary,'-d',str(device),'-f',str(freq),'-s',str(rate),'-g',str(gain),'-n',str(pairs),'-']
    start=time.monotonic(); received=0; status='early-eof'; rc=None
    with tempfile.TemporaryFile(mode='w+b') as err:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err)
        try:
            with (out/'continuous.cu8').open('wb') as f:
                while received<expected:
                    wait=seconds+timeout_extra-(time.monotonic()-start)
                    if wait<=0: status='timeout';break
                    ready,_,_=select.select([proc.stdout],[],[],wait)
                    if not ready:status='timeout';break
                    buf=os.read(proc.stdout.fileno(),min(262144,expected-received))
                    if not buf:break
                    f.write(buf);received+=len(buf)
            if received==expected:status='bounded-complete'
        finally:
            if proc.poll() is None:proc.terminate()
            try:rc=proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();rc=proc.wait()
            proc.stdout.close()
        err.seek(0);stderr=err.read().decode('utf-8','replace')
    (out/'rtl_stderr.txt').write_text(stderr,encoding='utf-8')
    metadata={'schema':'virgo-rng-continuous-v1','created_utc':datetime.now(timezone.utc).isoformat(),'setup':setup,'rate':rate,'freq':freq,'gain_requested':gain,'seconds_requested':seconds,'pairs_requested':pairs,'bytes_received':received,'capture_status':status,'rtl_returncode_after_termination':rc,'pll_not_locked': 'PLL not locked' in stderr,'elapsed_wall_seconds':time.monotonic()-start,'note':'Intentional termination after byte target; return code may be negative.'}
    (out/'capture_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    if status!='bounded-complete':raise RuntimeError(f'Capture incomplete: {status}, {received}/{expected} bytes; see {out}')
    window_pairs=int(window_seconds*rate)
    if window_pairs<2:raise ValueError('window_seconds too small')
    analyze_file(out/'continuous.cu8',rate=rate,window_pairs=window_pairs,output=out,plot=plot)
    return metadata
