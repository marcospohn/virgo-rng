# Virgo-RNG v1.20 — Diagnóstico temporal e espectral I/Q

A versão 1.20 acrescenta `spectral-iq`, que compara autocorrelação de I e Q, correlação cruzada I/Q (lags -64 a +64), densidades espectrais de potência Welch e coerência espectral quadrática. A análise é **descritiva**, sem testes de significância ou alegações de independência, entropia criptográfica ou origem astronômica.

## Instalar no Ubuntu

```bash
unzip virgo_rng_v120.zip
cd virgo_rng_v120
bash instalar_e_executar_virgo_rng_v120.sh install
```

A instalação completa instala pacotes Ubuntu, Python, dependências e ferramentas de referência NIST, necessitando internet. Caso já tenha Python e dependências, pode executar `python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[plot,test]'` sem compilar o NIST.

## Analisar as duas capturas anteriores (não exige novo hardware)

```bash
bash instalar_e_executar_virgo_rng_v120.sh spectral-iq ../continuous-primeira.cu8 results/espectro_primeira
bash instalar_e_executar_virgo_rng_v120.sh spectral-iq ../continuous-segunda.cu8 results/espectro_segunda
```

Ajuste os caminhos conforme onde estão os arquivos. Cada execução gera `spectral_report.json` e `spectral_plot.png` (com matplotlib). Envie os dois relatórios e, se possível, as duas figuras.

A configuração padrão analisa 12 janelas distribuídas pelo arquivo, cada uma com 262144 pares I/Q, ou aproximadamente 1,31% de 180 s a 2,4 MS/s. Não representa cobertura completa. Para ampliar cobertura, aumente `JANELAS` e/ou `PARES_POR_JANELA` (múltiplo de 4096); os segmentos devem caber no arquivo. A análise espectral usa FFT de 4096 pontos e segmentos sem sobreposição. Coerência mede dependência linear em frequência e não mede toda dependência estatística. A amostragem de janelas espaçadas não demonstra estacionariedade.

## Atenção

A v1.19 usou quantização de 4 bits na estimativa de informação mútua. A v1.20 trabalha diretamente com os bytes I/Q originais e mede **correlação linear**, uma grandeza diferente. Comparar picos de informação mútua e de correlação exige cautela. Nenhuma captura SDR física foi realizada durante o desenvolvimento.
