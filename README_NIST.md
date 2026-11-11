# Virgo-RNG v1.1 — NIST SP 800-90B reference integration

This release does **not** reimplement NIST estimators. It prepares unconditioned, byte-encoded I/Q sequences and invokes an **external official NIST executable**, storing full tool output and SHA-256 hashes for provenance. The external NIST source is NOT bundled.

## Ubuntu setup

```bash
sudo apt update
sudo apt install -y git build-essential libbz2-dev libdivsufsort-dev libjsoncpp-dev libssl-dev libmpfr-dev libgmp-dev
# Install Virgo-RNG:
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test,plot]'
pytest -q
# Obtain and compile reference tools:
git clone https://github.com/usnistgov/SP800-90B_EntropyAssessment.git
cd SP800-90B_EntropyAssessment/cpp
make non_iid
make iid
# Check locations of ea_non_iid and ea_iid; they are typically in cpp/
cd ../..
```

## Prepare independent I/Q sequences (NO filtering or conditioning)

```bash
virgo-rng nist-prepare antenna_01_sample.cu8 --out-dir results/nist --setup indoor-dipole
```

This produces `i_symbols.bin`, `q_symbols.bin` and `manifest.json`. Each byte is one 8-bit symbol. This is NOT the SHA-256 conditioned output. `--skip-pairs N` is available only for documented sensitivity analysis; never silently remove startup anomalies. `--max-pairs` limits data explicitly.

## Invoke reference NIST estimator

```bash
virgo-rng nist-run results/nist/i_symbols.bin --binary ./SP800-90B_EntropyAssessment/cpp/ea_non_iid --report results/nist/i_non_iid.json
virgo-rng nist-run results/nist/q_symbols.bin --binary ./SP800-90B_EntropyAssessment/cpp/ea_non_iid --report results/nist/q_non_iid.json
```

For exploratory IID testing, replace `ea_non_iid` with `ea_iid`. Do not claim IID on this basis alone. Commands use `-i -t` to assess raw data and truncate bitstring assessment to 1M bits; the symbol sequence is not truncated by `-t`. The tool may require significant RAM/time; use `--timeout` to control duration. The wrapper reports failures and retains stderr.

## Important scientific limitations

- I and Q originate from the same receiver and can be correlated. Do not add their entropy estimates.
- Estimates on an indoor dipole capture do not establish an astronomical origin of entropy.
- Restart datasets require **independent physical receiver restarts**, not merely dividing one file into segments.
- SP800-90B source validation additionally requires a source model, justified IID/non-IID selection, health tests, restart analysis, and conditioning assessment.
- This integration provides no certification and does not automatically choose an extraction rate.
- Do not use outputs for cryptographic keys.

Official source: https://github.com/usnistgov/SP800-90B_EntropyAssessment
Specification: https://csrc.nist.gov/pubs/sp/800/90/b/final
