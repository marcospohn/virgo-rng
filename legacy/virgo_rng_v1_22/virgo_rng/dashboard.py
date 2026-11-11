"""Local-only, read-only experimental dashboard for offline CU8 and live RTL-SDR."""
import json
import shutil
import subprocess
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .stream import summarize_chunk

class Monitor:
    def __init__(self, *, source=None, live=False, rate=2400000, freq=1420405752, gain=None,
                 seconds=30, chunk_bytes=65536, setup='unknown', interval=0.05, max_windows=300):
        if (source is None) == (not live):
            raise ValueError('Specify exactly one source: file or live')
        if chunk_bytes < 512 or chunk_bytes % 2 or max_windows < 1 or interval < 0 or seconds <= 0:
            raise ValueError('Invalid monitoring settings')
        if live and (not 225001 <= rate <= 3200000 or freq <= 0 or seconds > 3600):
            raise ValueError('Invalid SDR settings')
        self.source=Path(source) if source is not None else None
        self.live=live; self.rate=rate; self.freq=freq; self.gain=gain; self.seconds=seconds
        self.chunk_bytes=chunk_bytes; self.setup=setup; self.interval=interval
        self.windows=deque(maxlen=max_windows); self.lock=threading.Lock()
        self.status='ready'; self.error=None; self.total_bytes=0; self.count=0
        self.stop_event=threading.Event(); self.thread=None; self.proc=None

    def start(self):
        if self.thread is not None: raise RuntimeError('Already started')
        self.thread=threading.Thread(target=self._run,daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()

    def _run(self):
        with self.lock: self.status='running'
        try:
            if self.live:
                if not shutil.which('rtl_sdr'): raise RuntimeError('rtl_sdr not installed')
                n=int(self.seconds*self.rate)
                cmd=['rtl_sdr','-f',str(self.freq),'-s',str(self.rate),'-n',str(n)]
                if self.gain is not None: cmd+=['-g',str(self.gain)]
                cmd+=['-']
                with subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL) as proc:
                    self.proc=proc
                    self._consume(proc.stdout,max_bytes=n*2,delay=0)
                    if self.stop_event.is_set(): proc.terminate()
                    code=proc.wait(timeout=10)
                    if code and not self.stop_event.is_set(): raise RuntimeError(f'rtl_sdr exit {code}')
            else:
                with self.source.open('rb') as f: self._consume(f,delay=self.interval)
            with self.lock: self.status='stopped' if self.stop_event.is_set() else 'completed'
        except Exception as exc:
            with self.lock: self.status='error'; self.error=str(exc)
        finally:
            self.proc=None

    def _consume(self,reader,*,max_bytes=None,delay=0):
        remaining=max_bytes
        while not self.stop_event.is_set():
            size=self.chunk_bytes if remaining is None else min(self.chunk_bytes,remaining)
            if size < 512: break
            parts=[]; got=0
            while got<size and not self.stop_event.is_set():
                part=reader.read(size-got)
                if not part: break
                parts.append(part); got+=len(part)
            if got<size:
                if remaining is not None and not self.stop_event.is_set():
                    raise EOFError(f'Unexpected SDR EOF ({got}/{size})')
                break
            stats=summarize_chunk(b''.join(parts),self.count)
            with self.lock:
                self.windows.append(stats); self.count+=1; self.total_bytes+=got
            if remaining is not None:
                remaining-=got
                if remaining==0: break
            if delay and self.stop_event.wait(delay): break

    def snapshot(self):
        with self.lock:
            return {'status':self.status,'error':self.error,'windows':list(self.windows),
                    'total_windows':self.count,'total_bytes':self.total_bytes,
                    'setup':self.setup,'source':'rtl_sdr' if self.live else str(self.source),
                    'security_status':'UNVALIDATED_NOT_FOR_CRYPTOGRAPHY',
                    'note':'Marginal histogram statistics and lag-1 autocorrelation; no entropy-rate bound'}


def serve(monitor,host='127.0.0.1',port=8765,open_browser=False):
    page=(Path(__file__).parent/'web'/'index.html').read_bytes()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path=urlparse(self.path).path
            if path=='/': data=page; kind='text/html; charset=utf-8'
            elif path=='/api/state': data=json.dumps(monitor.snapshot(),allow_nan=False).encode(); kind='application/json'
            else: self.send_error(404); return
            self.send_response(200); self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers(); self.wfile.write(data)
        def log_message(self,*args): pass
    server=ThreadingHTTPServer((host,port),Handler)
    monitor.start()
    url=f'http://{host}:{server.server_port}/'
    print('Virgo-RNG v1.0 dashboard:',url,flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try: server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt: pass
    finally:
        server.shutdown(); server.server_close(); monitor.stop()
        if monitor.thread: monitor.thread.join(timeout=3)
