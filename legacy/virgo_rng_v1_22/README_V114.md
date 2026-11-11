# Virgo-RNG v1.14 — contribuição preditiva cruzada I/Q

Esta versão responde à pergunta: **quanto o histórico do canal Q acrescenta à previsão de I, além do histórico de I?** E vice-versa.

## Instalação no Ubuntu

```bash
unzip virgo_rng_v114.zip
cd virgo_rng_v114
bash instalar_e_executar_virgo_rng_v114.sh install
```

## Análise offline

```bash
bash instalar_e_executar_virgo_rng_v114.sh cross-channel /CAMINHO/PARA/continuous.cu8
```

O programa usa 12 janelas de 120.000 pares (padrão), com 70% de treino e 30% de teste cronológico, e símbolos de 2 bits por componente. Compara a log-loss de preditores condicionados somente no histórico do canal alvo e em históricos de **ambos os canais**, com 1, 2 e 4 amostras anteriores. Usa suavização do modelo conjunto com a previsão do próprio canal como referência. Para controle, desloca circularmente Q de forma aleatória, preservando sua estrutura temporal e quebrando o alinhamento com I.

Saídas: `cross_channel_report.json` e `cross_channel_plot.png`.

**Interpretação:** ganho positivo significa melhor previsão fora do treinamento com o outro canal. Ganho zero ou negativo não prova independência; a quantização, o modelo e o volume finito de treino podem ocultar dependências. O controle circular pode reter efeitos lentos comuns. Nenhuma medida constitui min-entropia validada, avaliação NIST ou taxa segura de extração. Para comparar resultados de I e Q, considerar o mesmo particionamento cronológico.

Os comandos e recursos anteriores permanecem disponíveis.
