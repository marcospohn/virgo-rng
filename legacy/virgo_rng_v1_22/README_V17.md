# Virgo-RNG 1.7 — stability and RF controls

This version analyzes **all 64 complete 4096-IQ-pair blocks** in each 262144-pair capture (v1.6.1 analyzed 32). It adds `first_vs_rest`, campaign comparison and coverage fields. These are descriptive statistics, not hypothesis tests or min-entropy bounds.

## Ubuntu

```bash
bash instalar_e_executar_virgo_rng_v17.sh install
bash instalar_e_executar_virgo_rng_v17.sh startup-dipole
bash instalar_e_executar_virgo_rng_v17.sh startup-load
```

Each campaign has 20 **operator-attested physical USB power cycles**. For each run disconnect USB power, wait >=5 seconds, reconnect and type `RESET`. The two campaigns are separate; don't move the antenna or RF chain while acquiring each set. The `startup-load` mode requires a suitable 50-ohm RF terminator at the SDR input; do not short the input. Document whether any SAWbird+ H1 and bias tee are present. **Disable bias tee before connecting a load unless the termination is explicitly rated for DC power.** Avoid connecting/disconnecting RF while powered.

For custom runs use `virgo-rng startup-collect --out-dir DIR --runs 20 --pairs 262144 --block-pairs 4096 --setup indoor-dipole` (or `50ohm-termination`). To reanalyze v1.6.1 raw data: `virgo-rng startup-analyze PATH_TO_OLD_CAMPAIGN` (writes a report there; copy it first if preservation matters). All output directories must be new. 20 restarts are exploratory and **not** NIST 1000x1000 restart testing. `PLL not locked!` in stderr is not proof of persistent unlock. First delivered bytes are not guaranteed first ADC bytes.
