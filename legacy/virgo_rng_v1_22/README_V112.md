# Virgo-RNG v1.12 — Joint I/Q temporal predictability

The new `joint-predictive` command uses **both I and Q together** as a single joint symbol. It reads the existing `continuous.cu8` without needing SDR hardware.

## Ubuntu installation

```bash
unzip virgo_rng_v112.zip
cd virgo_rng_v112
bash instalar_e_executar_virgo_rng_v112.sh install
```

## Run

```bash
bash instalar_e_executar_virgo_rng_v112.sh joint-predictive /ABSOLUTE/PATH/continuous.cu8
```

Or run directly after activation:

```bash
. .venv/bin/activate
virgo-rng joint-predictive /ABSOLUTE/PATH/continuous.cu8 --out-dir results/joint_v112 \
  --windows 12 --sample-pairs 120000 --shuffle-repeats 3
```

Outputs: `joint_predictive_report.json` and `joint_predictive_plot.png`.

## Method and caveats

- The **upper 2 bits** of I and of Q are concatenated into one **4-bit joint symbol** (16 possibilities). This is **not** the original 16-bit I/Q pair. Optional `--quantization-bits 1` makes 2-bit joint symbols.
- Hierarchical smoothed n-gram backoff uses previous **0, 1, 2, 4, or 8 I/Q pairs**. For each context order it interpolates with the immediately lower-order model using pseudocount strength 30. Training is first 70%, testing last 30%, with an 8-pair embargo between.
- Each window is analyzed independently. Twelve windows spread across the recording are selected; the first 120,000 pairs of each window are processed. The entire 864 MB recording is **not** processed as one predictive sequence.
- Three shuffled controls per window permute **whole joint I/Q symbols**, keeping simultaneous I/Q dependence but destroying temporal order. Random seed is fixed for reproducibility.
- Predictive gains are held-out reductions in log loss in bits per **quantized joint symbol**. They are **not** Shannon entropy rates, min-entropy, certified extractable bits, or an SP 800-90B assessment.
- A gain of zero does not prove statistical independence. Backoff models can miss longer or nonlinear dependencies. Controls are exploratory and do not establish statistical significance by themselves.
- No physical 50-ohm RF termination is required for this offline analysis.

Send the JSON report and PNG plot for interpretation.
