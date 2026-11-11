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
