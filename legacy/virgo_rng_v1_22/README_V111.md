# Virgo-RNG v1.11 — previsibilidade temporal de ordem superior

Analisa offline o `continuous.cu8` anterior, sem nova captura, carga RF ou reinicialização.

## Ubuntu

```bash
unzip virgo_rng_v111.zip
cd virgo_rng_v111
bash instalar_e_executar_virgo_rng_v111.sh install
bash instalar_e_executar_virgo_rng_v111.sh predictive-dependence /CAMINHO/continuous.cu8
```

A análise padrão seleciona até 12 janelas uniformemente distribuídas nos 180 s, utilizando os primeiros 120.000 pares I/Q de cada janela. Cada canal é quantizado de 8 para 4 bits (16 símbolos). Um modelo de frequência condicional com suavização estima probabilidades dadas 1, 2, 4 e 8 amostras anteriores. Treina cronologicamente nos primeiros 70% de cada trecho e mede *log-loss* nos últimos 30%, excluindo históricos na fronteira. Um controle embaralhado com semente reprodutível é comparado. `predictive_gain_bits` = perda média do preditor marginal menos perda do preditor contextual, **em bits por símbolo quantizado**; valores negativos indicam piora preditiva. Os resultados não são entropia condicional de Shannon, nem min-entropia.

Arquivos gerados: `predictive_report.json`, `predictive_plot.png`.

O instalador também preserva os comandos anteriores e executa testes automatizados. A instalação completa requer Ubuntu com rede para dependências e fontes NIST; para ambiente já instalado, `. .venv/bin/activate && pip install -e '.[plot,test]'` pode bastar.

**Limitações:** análise exploratória com quantização, contextos raros e forte esparsidade para históricos de 8 símbolos; seleção sistemática de janelas; dependência do modelo e de seu hiperparâmetro de suavização. O controle embaralhado não constitui teste formal de independência. O NIST SP 800-90B exige procedimentos e dados específicos; estes números não são uma avaliação validada de min-entropia nem autorizam dimensionar um extrator criptográfico.
