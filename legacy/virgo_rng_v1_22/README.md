# Virgo-RNG v1.5 — Restart audit and critical correction

This release adds `virgo-rng restart-audit` for offline checks of the restart journal, captured CU8 hashes, run counts, and I/Q matrices. It **cannot** prove physical power cycling or NIST compliance.

**Important fix:** v1.4 `restart-evaluate` used an undefined `current_h` variable and passed `--h-i` to the Q evaluation. v1.5 corrects both, with a regression test using separate I and Q entropy parameters. **Do not use v1.4 to run restart-evaluate.**

Install (Ubuntu): `bash instalar_e_executar_virgo_rng_v15.sh install`

Trial: `bash instalar_e_executar_virgo_rng_v15.sh trial` then `bash instalar_e_executar_virgo_rng_v15.sh pack-trial` then `bash instalar_e_executar_virgo_rng_v15.sh audit-trial`.

For a physically verified full campaign: `collect-full`, `pack-full`, `audit-full`, `evaluate-full`. A three-run trial is not eligible for official NIST restart assessment. Review `README_RESTART.md` before a full campaign. Use caution when powering USB devices; software cannot attest hardware restart or guarantee capture of the earliest samples.

The official NIST C++ implementation is downloaded/compiled by the install script, not redistributed in this archive. No entropy source certification is claimed.

## v1.6 — Startup characterization

Leia [README_STARTUP.md](README_STARTUP.md). O script `instalar_e_executar_virgo_rng_v16.sh` instala, testa e executa um ensaio de 3 ciclos físicos atestados pelo operador, gerando capturas brutas, relatório JSON e gráficos.


**v1.6.1:** corrige captura sem limite: streaming binário com tamanho exato e encerramento controlado. Consulte README_STARTUP.md.
