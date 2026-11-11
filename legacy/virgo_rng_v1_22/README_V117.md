# Virgo-RNG v1.17 — auditoria retrospectiva dos testes de informação mútua

A v1.17 acrescenta `audit-lags` para comparar os relatórios da captura exploratória e da replicação. Não requer os arquivos .cu8, nem nova captura.

## Uso Ubuntu

```bash
unzip virgo_rng_v117.zip
cd virgo_rng_v117
bash instalar_e_executar_virgo_rng_v117.sh install
bash instalar_e_executar_virgo_rng_v117.sh audit-lags /caminho/primeiro/global_lag_mi_report.json /caminho/segundo/global_lag_mi_report.json
```

Saída: `results/audit117/audit_report.json`.

**O que é testado:** comparabilidade dos parâmetros; contraste entre defasagens ±8 identificadas na captura exploratória e testadas na replicação; correção de Holm para dois valores-p pontuais da replicação; diferença nos limiares globais.

**Limitação central:** a correção de Holm só controla erro familiar se os valores-p pontuais forem válidos. Deslocamentos circulares podem não formar um nulo válido quando há não-estacionariedade, periodicidade ou interferência compartilhada. Os JSON originais não incluem as distribuições completas das permutações; portanto não permitem auditar a validade nem recalcular os valores-p. Um resultado nominalmente significativo após Holm não prova dependência física. Não atribuir min-entropia criptográfica.

Para auditoria mais forte: guardar vetores completos de máximos nulos e estatísticas por controle, executar novos controles por blocos e replicar em capturas independentes, além de documentar PLL e cadeia RF.
