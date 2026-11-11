# Virgo-RNG v1.10 — dependência temporal

Análise offline do `continuous.cu8` já capturado. Não requer nova aquisição nem terminador de 50 ohms.

## Ubuntu

```bash
unzip virgo_rng_v110.zip
cd virgo_rng_v110
bash instalar_e_executar_virgo_rng_v110.sh install
bash instalar_e_executar_virgo_rng_v110.sh temporal-dependence /CAMINHO/continuous.cu8
```

Para usar ambiente virtual já preparado: `. .venv/bin/activate` e `virgo-rng temporal-dependence /CAMINHO/continuous.cu8 --out-dir results/td`.

Saídas: `temporal_dependence_report.json` e `temporal_dependence_plot.png`.

Por padrão: janelas de 1 s com 200.000 pares I/Q contíguos do começo de cada janela. Mede H(I_n|I_(n-1)) e H(Q_n|Q_(n-1)) em 8 bits e, como diagnóstico exploratório, H((I,Q)_n|(I,Q)_(n-1)) após quantização de 4 bits por componente. A quantização não preserva o valor da entropia original. Estimadores plug-in podem ter viés, especialmente para distribuições condicionais grandes. Não há inferência de min-entropia, independência criptográfica nem extração de bits.

Não envie o arquivo bruto de 864 MB: apenas os dois arquivos de resultados.
