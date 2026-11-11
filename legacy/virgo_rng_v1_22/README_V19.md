# Virgo-RNG v1.9 — Dependência entre I e Q

Analisa offline um arquivo CU8 (bytes I0,Q0,I1,Q1,...), sem adquirir novas amostras.

## Instalação no Ubuntu

```bash
unzip virgo_rng_v19.zip
cd virgo_rng_v19
bash instalar_e_executar_virgo_rng_v19.sh install
```

## Análise dos dados já coletados

```bash
bash instalar_e_executar_virgo_rng_v19.sh iq-dependence /CAMINHO/PARA/continuous.cu8
```

A saída aparece em `results/iq_dependence_.../` com `dependence_report.json` e `dependence_plot.png`.

Alternativa direta: `.venv/bin/virgo-rng iq-dependence /CAMINHO/PARA/continuous.cu8 --out-dir results/iq_01`.

A entropia marginal e conjunta usa TODOS os pares I/Q por histograma 256x256, em leitura por blocos (não carrega os 864 MB de uma vez). A correlação temporal e cruzada usa os primeiros 200.000 pares consecutivos, configurável com `--lag-pairs`; por padrão, até 32 atrasos.

### Limitações

- Entropia de Shannon **não** é min-entropia; informação mútua e correlação não provam segurança criptográfica.
- Correlação zero não garante independência.
- Amostras temporais compartilham dependências; não somar entropias como bits criptográficos disponíveis.
- O estudo não identifica origem física do ruído nem valida NIST SP 800-90B.
- Se possível, enviar `dependence_report.json` e `dependence_plot.png` para discussão dos resultados.
