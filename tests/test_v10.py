import io
import json
import time
from urllib.request import urlopen
from threading import Thread
from http.server import ThreadingHTTPServer
import numpy as np
import pytest
from virgo_rng.dashboard import Monitor


def test_offline_playback(tmp_path):
    p=tmp_path/'iq.cu8'; p.write_bytes(np.random.default_rng(4).integers(0,256,8192,dtype=np.uint8).tobytes())
    m=Monitor(source=p,chunk_bytes=1024,interval=0,max_windows=3,setup='indoor-dipole')
    m.start();m.thread.join(timeout=5)
    d=m.snapshot()
    assert d['status']=='completed' and d['total_windows']==8
    assert d['total_bytes']==8192 and len(d['windows'])==3
    assert d['windows'][-1]['index']==7
    assert d['security_status']=='UNVALIDATED_NOT_FOR_CRYPTOGRAPHY'


def test_invalid_config():
    with pytest.raises(ValueError): Monitor()
    with pytest.raises(ValueError): Monitor(source='a',live=True)
    with pytest.raises(ValueError): Monitor(source='a',chunk_bytes=511)


def test_missing_file():
    m=Monitor(source='/path/that/does/not/exist',interval=0)
    m.start();m.thread.join(timeout=5)
    assert m.snapshot()['status']=='error'


def test_early_stop(tmp_path):
    p=tmp_path/'iq.cu8';p.write_bytes(bytes(range(256))*200)
    m=Monitor(source=p,chunk_bytes=512,interval=1)
    m.start()
    for _ in range(100):
        if m.snapshot()['total_windows']:break
        time.sleep(.01)
    m.stop();m.thread.join(timeout=5)
    assert m.snapshot()['status']=='stopped'
