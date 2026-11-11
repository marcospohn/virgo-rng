# Virgo-RNG v1.8 — estabilidade temporal (pesquisa exploratória)

Uma captura **contínua** de 180 s, sem reinicialização USB. Os dados CU8 brutos são armazenados integralmente (~864 MB a 2,4 MS/s). A aquisição termina por contagem exata de bytes, não depende de `rtl_sdr -n`. Os dados são processados em janelas de 1 s, com estatísticas separadas I/Q (Shannon empírica, desvio-padrão, média, autocorrelação lag-1, moda e símbolos distintos). O relatório inclui hash SHA-256, status, logs do driver e gráficos.

**Instalação Ubuntu:** `bash instalar_e_executar_virgo_rng_v18.sh install`

**Dipolo:** `bash instalar_e_executar_virgo_rng_v18.sh temporal-dipole` (180 s por padrão). Para teste menor: `bash instalar_e_executar_virgo_rng_v18.sh temporal-dipole results/teste_30s 30`.

**Carga 50 ohms:** `bash instalar_e_executar_virgo_rng_v18.sh temporal-load` — apenas após verificar bias tee desligado e terminador RF seguro.

**Análise offline:** `bash instalar_e_executar_virgo_rng_v18.sh temporal-analyze results/SEU_DIR/continuous.cu8 results/reanalise`

**Arquivos para enviar:** `temporal_report.json`, `capture_metadata.json` e, se possível, `rtl_stderr.txt` e `temporal_plot.png`. Não é necessário enviar `continuous.cu8` (arquivo grande). Preserve o CU8 localmente.

**Limitações:** entropia de Shannon não é estimativa conservadora de min-entropia; não prova fonte astronômica ou qualidade criptográfica. O aviso `PLL not locked!` é preservado, não interpretado como falha persistente sem diagnóstico. Amostras iniciais entregues pelo driver podem não ser as primeiras do ADC. A duração do arquivo é determinada pela taxa nominal, não por relógio de hardware calibrado.
