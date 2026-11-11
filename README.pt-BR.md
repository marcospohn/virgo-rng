# Virgo-RNG — código e dados de pesquisa

Este pacote reúne o **Virgo-RNG 2.0.0**, os scripts da campanha E1–E7, testes e **resultados numéricos processados** disponíveis. Não inclui fontes LaTeX, PDF, figuras ou fotografias do artigo.

**Não estão aqui os CU8 integrais de E1–E7** (esses arquivos permaneceram no Mac do pesquisador). Há uma amostra curta de I/Q em `data/samples/`. As medições de entropia são exploratórias e a origem galáctica dos excessos espectrais não está confirmada.

Para instalar:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,plot]'
python -m pytest -q tests
```

O programa principal é `virgo-rng-lab` (consulte `--help`). Para publicar na sua conta GitHub, consulte **[docs/COMO_PUBLICAR_GITHUB.md](docs/COMO_PUBLICAR_GITHUB.md)**. Antes de tornar público, escolha a licença e confira possíveis dados sensíveis em metadados.

<!-- BEGIN VIRGO-UPSTREAM-ATTRIBUTION -->
## Relação com o Virgo original e licença

O espectrômetro **Virgo**, originalmente desenvolvido por **Apostolos Spanakis-Misirlis**, é distribuído sob a licença **GNU GPL v3**: https://github.com/0xCoto/Virgo. Publicação: Spanakis-Misirlis, Van Eck e Boven (2021), *JOSS*, DOI: https://doi.org/10.21105/joss.03067.

**Virgo-RNG é um projeto de pesquisa separado**, e esta distribuição não inclui intencionalmente a árvore de código-fonte do Virgo original. Isso não equivale a uma auditoria integral de similaridade/proveniência. Se houver incorporação de código GPL de terceiros, devem ser respeitadas as obrigações da licença. Veja [a documentação de atribuição e licenciamento](docs/UPSTREAM_VIRGO.md). O código e os dados próprios **ainda não receberam uma licença neste pacote**.
<!-- END VIRGO-UPSTREAM-ATTRIBUTION -->
