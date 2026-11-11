import json
import pytest
from virgo_rng.nist_campaign import prepare_campaign, summarize_campaign, parse_estimates


def test_parser():
    x='H_original: 5.312354\nH_bitstring: 0.506069\nmin(H_original, 8 X H_bitstring): 4.048552'
    assert parse_estimates(x)=={'h_original':5.312354,'h_bitstring':0.506069,'h_final':4.048552}


def test_prepare_and_summary(tmp_path):
    source=tmp_path/'source.cu8'
    source.write_bytes(bytes(range(256))*23438) # 6,000,128 bytes, 3,000,064 IQ pairs
    out=tmp_path/'campaign'
    m=prepare_campaign(source,out,pairs_per_segment=1000000,setup='indoor-dipole')
    assert len(m['inputs'])==7
    assert (out/'beginning_i.bin').read_bytes()[:3]==bytes([0,2,4])
    assert (out/'beginning_q.bin').read_bytes()[:3]==bytes([1,3,5])
    assert (out/'full_iq_interleaved.bin').read_bytes()==source.read_bytes()
    assert all(x['status']=='not_run' for x in summarize_campaign(out)['results'])


def test_short_input(tmp_path):
    source=tmp_path/'small.cu8'; source.write_bytes(b'\0'*20)
    with pytest.raises(ValueError): prepare_campaign(source,tmp_path/'out')
