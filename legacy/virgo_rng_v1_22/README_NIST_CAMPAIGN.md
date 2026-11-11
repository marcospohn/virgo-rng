# Virgo-RNG v1.2: SP 800-90B within-recording sensitivity campaign

This does **not** implement NIST estimators; it uses the official `ea_non_iid` executable compiled by the user. No certification or restart test is implied.

## Prepare and optionally run

```bash
virgo-rng nist-campaign antenna_01_sample.cu8 --out-dir results/campaign12 \
  --pairs-per-segment 1000000 --setup indoor-dipole \
  --reference-i i_non_iid.json --reference-q q_non_iid.json
# Run 7 official evaluations (can take several minutes):
virgo-rng nist-campaign antenna_01_sample.cu8 --out-dir results/campaign12 \
  --pairs-per-segment 1000000 --setup indoor-dipole \
  --reference-i i_non_iid.json --reference-q q_non_iid.json \
  --binary ./SP800-90B_EntropyAssessment/cpp/ea_non_iid
virgo-rng nist-campaign-summary results/campaign12 --out results/campaign12/summary.json
```

The campaign generates beginning/middle/end non-overlapping segments, each with 1 million raw 8-bit samples per channel, and one full interleaved IQ file (10 million byte symbols for the 5-million-pair reference recording). The interleaved estimate **cannot** be compared to the sum of separate I and Q estimates. Every input is hashed and the manifest records exact offsets. Existing full-capture results are carried as **references**, not silently re-evaluated.

Note: The official `-t` option truncates the bitstring assessment to one million bits; the wrapper records this. Compare results with that constraint explicitly.

A single recording does not supply independent restarts. Statistical estimates are not validated entropy rates, and must not determine cryptographic output rates without further assessment.
