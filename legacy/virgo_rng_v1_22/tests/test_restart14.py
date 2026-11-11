import json
import stat
import pytest
from virgo_rng.restart14 import evaluate
from virgo_rng.nist90b import sha256


def test_reject_small_trial(tmp_path):
    folder=tmp_path/'trial';folder.mkdir()
    (folder/'config.json').write_text(json.dumps({'runs_requested':3,'samples_per_run':1000}))
    (folder/'restart_manifest.json').write_text(json.dumps({'runs':3,'samples_per_run':1000,'source_config_sha256':sha256(folder/'config.json')}))
    binary=tmp_path/'ea_restart';binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o755)
    with pytest.raises(ValueError,match='1000'):
        evaluate(folder,binary=str(binary),h_i=4.0,ack_physical_restarts=True)


def test_require_attestation_and_entropy(tmp_path):
    with pytest.raises(ValueError,match='attested'):
        evaluate(tmp_path,h_i=4.0)
    with pytest.raises(ValueError,match='H_I'):
        evaluate(tmp_path,h_i=0,ack_physical_restarts=True)
    with pytest.raises(ValueError,match='H_Q'):
        evaluate(tmp_path,h_i=4,h_q=9,ack_physical_restarts=True)


def test_reject_wrong_binary(tmp_path):
    with pytest.raises(ValueError,match='ea_restart'):
        evaluate(tmp_path,binary='ea_non_iid',h_i=4,ack_physical_restarts=True)
