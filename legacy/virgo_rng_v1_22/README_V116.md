# Virgo-RNG v1.16 — Teste global de dependência I/Q

Compara o maior excesso de informação mútua entre 65 defasagens com a distribuição do máximo em controles de deslocamento circular de Q. Corrige **a seleção do maior lag** dentro da família testada. O p-valor é aproximado e depende da validade do controle temporal.

## Instalação Ubuntu

```bash
unzip virgo_rng_v116.zip
cd virgo_rng_v116
bash instalar_e_executar_virgo_rng_v116.sh install
```

## Executar com a mesma captura

```bash
bash instalar_e_executar_virgo_rng_v116.sh global-lag-mi /CAMINHO/continuous.cu8
```

Opcionalmente: `global-lag-mi /CAMINHO/continuous.cu8 results/global 999` para 999 permutações (demorado). Por padrão: 12 janelas de 30000 pares, 4 bits/componente, lags ±32, 199 permutações. **Não compare diretamente a magnitude da MI com a v1.15**, que usou 120000 pares/janela: o viés amostral muda. Uma nova captura não é necessária.

Saídas: `global_lag_mi_report.json`, `global_lag_mi_plot.png`. Envie ambos para avaliação.

## Limitações

O controle desloca circularmente Q em cada janela, preservando sua ordem temporal, mas não garante hipótese nula intercambiável em presença de deriva, periodicidade ou interferência. As janelas de uma captura não equivalem a aquisições independentes. Significância não prova causa física nem segurança criptográfica. Repita com outras capturas, taxas e ganhos e, quando disponível, terminador RF de 50 ohms com bias tee desligado.
