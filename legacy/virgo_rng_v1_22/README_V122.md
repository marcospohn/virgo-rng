# Virgo-RNG v1.22 — cobertura integral das correlações I/Q

O modo `persistence-iq` continua a amostrar 120 janelas **distribuídas por todo o arquivo** (modo esparso). O novo modo `persistence-full` percorre sequencialmente **todas as janelas completas e não sobrepostas** de 65.536 pares I/Q. O relatório inclui cobertura, total de pares e pares não analisados (sobras finais). As correlações são descritivas; não constituem estimativa de min-entropia nem atribuição de origem física.

## Instalação Ubuntu

```bash
unzip virgo_rng_v122.zip
cd virgo_rng_v122
bash instalar_e_executar_virgo_rng_v122.sh install
```

## Analisar os três arquivos já coletados

```bash
bash instalar_e_executar_virgo_rng_v122.sh persistence-full /home/REDACTED_USER/virgo-gain-experiment/gain10.cu8 results/gain10_full
bash instalar_e_executar_virgo_rng_v122.sh persistence-full /home/REDACTED_USER/virgo-gain-experiment/gain30.cu8 results/gain30_full
bash instalar_e_executar_virgo_rng_v122.sh persistence-full /home/REDACTED_USER/virgo-gain-experiment/gain40.cu8 results/gain40_full
```

Arquivos produzidos: `persistence_report.json`, `persistence_plot.png`. Envie os três JSONs para comparação. Para análise rápida/esparsa: `bash instalar_e_executar_virgo_rng_v122.sh persistence-iq ARQUIVO.cu8 DIRETORIO 120 65536`.

**Observações:** a varredura integral de arquivos grandes demora mais e gera relatórios e gráficos volumosos. Cada janela contém 65.536 pares e, a 2,4 MS/s, dura aproximadamente 27,3 ms; as 120 janelas do modo esparso são distribuídas ao longo de toda a gravação, não contíguas. Não use o índice de janela como tempo em segundos. Mantenha o SAWbird+ H1 e a configuração documentados para interpretar os resultados; teste sem o amplificador separadamente, se desejar.
