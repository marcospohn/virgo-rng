# Virgo-RNG v1.6 — caracterização das primeiras amostras entregues pelo driver

Objetivo: investigar transientes iniciais de I/Q e mensagens `PLL not locked!` sem alegar medir as primeiras amostras do ADC ou demonstrar conformidade NIST.

## Ubuntu

```bash
bash instalar_e_executar_virgo_rng_v16.sh install
bash instalar_e_executar_virgo_rng_v16.sh startup-trial
```

**Antes de digitar `RESET` a cada uma das três rodadas:** desconecte fisicamente a alimentação USB, aguarde pelo menos 5 segundos, reconecte e espere o dispositivo aparecer. Digitar apenas `RESET` não é reinicialização física. Use um diretório diferente por ensaio (o script gera um nome com horário UTC).

Para reanalisar: `bash instalar_e_executar_virgo_rng_v16.sh startup-analyze results/startup_YYYYMMDDTHHMMSSZ`.

## Saídas

- `config.json`: parâmetros, executável, hash e limitações
- `runs.jsonl`: uma entrada por captura, incluindo stderr e flag de aviso PLL
- `startup_0000.cu8` etc.: bytes I/Q originais, sem condicionamento
- `startup_report.json`: médias, desvios-padrão, entropia **Shannon empírica** e autocorrelação lag 1 por bloco, com comparações primeiro/último bloco
- `startup_0000.png` etc.: gráficos por execução

Por padrão são 262.144 pares I/Q por execução (aprox. 109 ms de amostragem nominal a 2,4 MS/s), analisados em blocos de 4.096 pares (~1,71 ms). O primeiro bloco é o primeiro **entregue pelo programa `rtl_sdr`**, não necessariamente o primeiro gerado pelo ADC após a energização. O driver pode inicializar o sintonizador, esperar a sintonia e descartar dados antes da captura. A duração do processo não equivale ao intervalo de aquisição.

O aviso `PLL not locked!` é registrado literalmente; sua presença não prova que o PLL permaneceu destravado durante a captura. As métricas exploratórias não estimam um limite inferior de min-entropia, não provam independência, nem validam geração criptográfica. Atestação de desligamento USB depende do operador; não há verificação elétrica independente.

## Execução manual avançada

```bash
source .venv/bin/activate
virgo-rng startup-collect --out-dir results/meu_ensaio --runs 3 --pairs 262144 --block-pairs 4096 --setup indoor-dipole
virgo-rng startup-analyze results/meu_ensaio
```

Não iniciar 1.000 reinicializações antes de revisar o comportamento inicial e confirmar as condições experimentais.


### Correção v1.6.1

O programa captura um número exato de bytes pelo stdout binário do `rtl_sdr` (`-`) e encerra o processo ao alcançar o limite. Assim não depende do encerramento automático do `rtl_sdr -n`. O código de retorno negativo após o encerramento intencional não é erro; `capture_status` registra `bounded-complete`. O método requer que o `rtl_sdr` suporte saída binária para `-`. O primeiro experimento v1.6 que excedeu o tamanho esperado deve ser preservado apenas para diagnóstico, não reutilizado como campanha válida.
