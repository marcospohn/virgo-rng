# Virgo-RNG v1.19 — auditoria exploratória por reorganização de blocos

Esta versão adiciona o comando `local-audit` sem alterar as funções anteriores. O objetivo é estudar a sensibilidade dos picos de informação mútua I/Q a um controle diferente de deslocamento circular.

## Ubuntu

```bash
unzip virgo_rng_v119.zip
cd virgo_rng_v119
bash instalar_e_executar_virgo_rng_v119.sh install
bash instalar_e_executar_virgo_rng_v119.sh local-audit /CAMINHO/PRIMEIRA/continuous.cu8 results/local_primeira 199 256
bash instalar_e_executar_virgo_rng_v119.sh local-audit /CAMINHO/SEGUNDA/continuous.cu8 results/local_segunda 199 256
```

A instalação completa inclui dependências Ubuntu, ambiente virtual, testes e compilação da suíte NIST 90B obtida da fonte oficial. Precisa de acesso à internet. Para um ambiente Python com dependências já instaladas, execute `python -m virgo_rng.audit119 ARQUIVO.cu8 --out-dir results/teste --permutations 199`.

Cada execução gera `local_audit_report.json`, `local_null_profiles.npz` e `local_audit_plot.png`.

O programa lê 12 segmentos de 32768 pares I/Q (de 180 segundos, apenas ~0,09% dos pares), distribuídos ao longo do arquivo. Quantiza cada componente em 4 bits, mede MI nos atrasos -32..32 e reorganiza blocos Q de 256 pares, mantendo I inalterado. A sequência temporal *dentro* de cada bloco Q é preservada, mas a sequência entre blocos é alterada. Os controles anteriores eram deslocamentos circulares e preservavam a ordem completa de Q; este novo controle é deliberadamente diferente.

**Atenção:** os valores-p calculados para os controles de blocos são exploratórios. Reorganizar blocos pode violar permutabilidade, destruir dependências internas de Q em fronteiras e introduzir outros vieses. Concordância com os controles circulares não prova validade da hipótese nula; divergência mostra sensibilidade. Momentos por janela não constituem um teste formal de estacionariedade. O experimento não estima min-entropia criptográfica nem atribui causalidade à radiação astronômica.

A versão mantém todos os recursos anteriores, incluindo `null-audit` v1.18. Para comparar, utilize exatamente os mesmos arquivos nas duas análises. Testes automatizados não substituem teste em SDR físico.
