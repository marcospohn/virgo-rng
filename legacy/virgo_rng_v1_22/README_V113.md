# Virgo-RNG v1.13 — triagem exploratória NIST SP 800-90B (não IID)

Esta versão **não implementa estimadores NIST**: chama o executável oficial `ea_non_iid`, sem modificar seus algoritmos. Os resultados **não certificam** a fonte nem fornecem uma taxa segura de extração.

## Instalar (Ubuntu)

```bash
unzip virgo_rng_v113.zip
cd virgo_rng_v113
bash instalar_e_executar_virgo_rng_v113.sh install
```

A instalação requer internet, `sudo`, bibliotecas de desenvolvimento e compila a ferramenta de referência pública NIST. O script executa os testes locais. A execução em hardware físico não é coberta por esses testes.

## Analisar a captura anterior

```bash
bash instalar_e_executar_virgo_rng_v113.sh nist-screen /CAMINHO/continuous.cu8
```

Opcionalmente, apenas preparar os arquivos (sem executar os estimadores):

```bash
bash instalar_e_executar_virgo_rng_v113.sh nist-prepare /CAMINHO/continuous.cu8
```

O programa seleciona **três intervalos não sobrepostos** (início, meio e fim), com **1 milhão de pares I/Q** em cada intervalo. Cada canal é extraído sem filtragem, normalização, embaralhamento ou condicionamento. São gerados seis arquivos de 1 milhão de símbolos de 8 bits cada, hashes SHA-256, saídas completas dos estimadores e `screen_summary.json`. O arquivo original não é alterado. Espaço adicional ~6 MB mais relatórios; o cálculo do hash da fonte lê o arquivo completo.

Se a ferramenta oficial falhar, o resumo registra falhas; não interprete estimativas ausentes como zero. O script pode demorar dependendo da CPU.

## Limitações científicas

- Cada segmento vem da **mesma aquisição**, não de reinicializações físicas independentes. Não satisfaz o teste de reinicialização do SP 800-90B.
- Não se deve somar os resultados de I e Q. A origem física comum e possíveis dependências temporais permanecem relevantes.
- As estimativas não estabelecem a origem astronômica do ruído nem excluem interferências controláveis por terceiros.
- A opção `-t` usada pelo wrapper oficial trunca a avaliação da representação em bits a 1 milhão de bits, não a sequência de símbolos.
- O valor mais baixo entre segmentos é um indicador exploratório, **não** um limite conservador certificado.
- Não gerar chaves criptográficas nem escolher taxa de extração com base apenas nesta triagem.

Fontes: https://csrc.nist.gov/pubs/sp/800/90/b/final e https://github.com/usnistgov/SP800-90B_EntropyAssessment
