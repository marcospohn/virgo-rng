# Virgo-RNG v1.15 — Informação mútua cruzada por defasagem

Investiga MI(I[t];Q[t-k]) para k de -32 a +32 (positivo: Q antecede I).

## Instalação (Ubuntu)
```bash
unzip virgo_rng_v115.zip
cd virgo_rng_v115
bash instalar_e_executar_virgo_rng_v115.sh install
```

## Executar com captura existente
```bash
bash instalar_e_executar_virgo_rng_v115.sh lag-mi /CAMINHO/continuous.cu8
```
Opcional: informar diretório de saída como terceiro argumento. Alternativamente, após ativar `.venv`, executar `virgo-rng lag-mi arquivo.cu8 --out-dir results/lag --max-lag 32 --quantization-bits 4 --control-repeats 10`.

## Saídas
- `lag_mi_report.json`: valores por defasagem e janela, controles e intervalos descritivos.
- `lag_mi_plot.png`: informação mútua observada, controles deslocados e excesso.

## Metodologia e limitações
12 janelas distribuídas na captura, 120 mil pares por janela; 4 bits mais significativos de cada canal por padrão. Estima MI por histograma conjunto, compara com 10 deslocamentos circulares aleatórios do canal Q por janela. Os deslocamentos preservam a sequência interna de Q e destroem o alinhamento local. O viés positivo de estimação pode ser relevante; usar excesso relativo aos controles. Os intervalos normais ponto a ponto não corrigem 65 testes simultâneos, e janelas da mesma captura não são independentes. Não interpretar um pico isolado como evidência confirmada; usar campanhas independentes e controle de múltiplas comparações. O resultado não mede min-entropia criptográfica nem prova origem física de uma dependência.

Não é necessário adquirir novamente nem possuir carga de 50 ohms para esta análise offline. O modo `install` requer internet para instalar dependências e compilar o NIST.
