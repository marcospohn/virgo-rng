# Virgo-RNG 2.0 — Plataforma consolidada de pesquisa I/Q

**Status:** versão funcional consolidada, **não certificada para uso criptográfico**. Mantém os comandos de pesquisa da v1.22 e adiciona uma interface de laboratório reproduzível.

## Instalação Ubuntu

```bash
unzip virgo_rng_v2_0_0.zip
cd virgo_rng_v2_0_0
bash instalar_e_executar_virgo_rng_v2.sh install
bash instalar_e_executar_virgo_rng_v2.sh init
```

## Estudo reproduzível

```bash
bash instalar_e_executar_virgo_rng_v2.sh study /caminho/gain30.cu8 results/gain30
bash instalar_e_executar_virgo_rng_v2.sh study-full /caminho/gain40.cu8 results/gain40
```

`study` amostra até 120 janelas distribuídas ao longo do arquivo, por padrão. `study-full` analisa **todas as janelas completas** e pode ser demorado e gerar JSON grande (ex.: milhares de janelas). O cálculo de entropia descritiva usa até 8 MB iniciais, independentemente do modo. Consulte `manifest.json` para a cobertura exata. Não misture cobertura de persistência com cobertura de entropia.

Cada execução gera `manifest.json` com SHA-256 do arquivo de entrada, configuração, cobertura e estado, `persistence/persistence_report.json`, `persistence/persistence_plot.png` quando matplotlib disponível, e `descriptive_entropy.json`. Diretórios de saída não podem conter arquivos prévios.

## Captura real

```bash
bash instalar_e_executar_virgo_rng_v2.sh capture results/captura.cu8 results/captura.json 180 virgo_config.json
```

A captura requer RTL-SDR conectado, utilitário `rtl_sdr`, permissões e driver funcional. **Não testado neste pacote em hardware físico.** Revise ganho, antena, bias tee e configuração antes da captura. Uma carga de 50 Ω não deve ser conectada a uma saída DC/bias tee energizada, salvo se expressamente adequada.

## Comandos avançados da versão anterior

Todos os subcomandos originais continuam disponíveis:

```bash
bash instalar_e_executar_virgo_rng_v2.sh legacy --help
bash instalar_e_executar_virgo_rng_v2.sh legacy nist-screen --help
bash instalar_e_executar_virgo_rng_v2.sh legacy global-lag-mi --help
```

Ferramentas de referência NIST (opcionais):

```bash
bash instalar_e_executar_virgo_rng_v2.sh nist-install
```

## Escopo científico e limitações

- A autocorrelação e as correlações I/Q são **descritores**, não medidas diretas de min-entropia.
- `naive_most_frequent_bound_bits` é somente a transformação da frequência empírica máxima; **não** é uma estimativa validada de min-entropia para fontes dependentes.
- A implementação antiga de condicionamento SHA-256 e os comandos `generate-*` são **experimentais** e não devem alimentar chaves ou aplicações de segurança.
- A origem cósmica da entropia não foi demonstrada. A cadeia RF, interferências, LNA, ADC e processamento digital podem contribuir.
- Um programa funcionalmente consolidado não equivale a uma fonte física validada conforme NIST SP 800-90B.
- A opção `full` pode exigir tempo e disco significativos. Janelas incompletas finais são explicitadas no relatório.
- Experimentos com carga de 50 Ω, reinicializações físicas e comparações com/sem SAWbird permanecem necessários para atribuição física e validação.

## Integridade e testes

```bash
bash instalar_e_executar_virgo_rng_v2.sh test
sha256sum arquivo.cu8
```

O teste automatizado não substitui ensaio de hardware. Para reprodutibilidade, mantenha arquivos CU8 originais imutáveis e compare `input_sha256`.
