# Reproducibility and acquisition provenance

## Baseline environment

Virgo-RNG main package v2.0.0: Python >=3.10; NumPy >=1.24. Optional Matplotlib and PyTest are declared in `pyproject.toml`. External NIST executables and SDR drivers are **not bundled**.

1. Install from the repository root using `python -m pip install -e '.[test,plot]'`.
2. Run `pytest -q tests` (offline tests do not demonstrate device validation).
3. Examine processed results under `data/processed/` and inspect the relevant scripts under `scripts/campaigns/`.
4. To rerun from raw, place the corresponding original recordings in local experiment directories, matching the filenames expected by the script. Do not reconstruct CU8 from processed CSV.
5. Do not treat time windows as independent astronomical replications; distinguish E5 reanalysis from its source E4 repetition.
6. For full reproducibility preserve sample rate, center frequencies, gain requests, azimuth/elevation, acquisition times, baseline width, DC removal method, filters and mask width.

## Data / scientific claims

- The narrow 1419.9886-MHz feature was strong with the antenna and retuning-consistent in frequency, but direction discrimination was not reproduced.
- The E5 Sagittarius broad feature near 1420.331 MHz was baseline-sensitive (at 50 kHz, reported integrated contrasts became negative).
- The Carina band near 1420.392 MHz yielded positive contrasts in the processed E6/E7 analyses after DC correction; neither a uniquely astronomical origin nor a certified entropy source has been established.
- Marginal Shannon entropy closely tracked the ADC sample amplitude dispersion; E7's global spectral-entropy association weakened after controlling for per-capture differences.

**These statements are descriptions of archived analyses and should not be treated as independently verified measurements of the inaccessible full CU8 files.**
