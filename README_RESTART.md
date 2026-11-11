# Virgo-RNG v1.4 — avaliação oficial de reinicialização

A coleta `restart-collect` requer **ciclos reais de alimentação** do RTL-SDR; reiniciar apenas o processo não é equivalente. A opção `--restart-command` executa um programa externo, mas o Virgo-RNG não consegue comprovar que ele desligou a alimentação USB.

## 1. Instalação

```bash
bash instalar_e_executar_virgo_rng_v14.sh install
```

## 2. Ensaio pequeno (não é NIST)

```bash
bash instalar_e_executar_virgo_rng_v14.sh trial
bash instalar_e_executar_virgo_rng_v14.sh pack-trial
```

## 3. Coleta real de 1000 ciclos

Apenas após verificar o comportamento do RTL-SDR e o mecanismo físico de desligamento:

```bash
bash instalar_e_executar_virgo_rng_v14.sh collect-full
bash instalar_e_executar_virgo_rng_v14.sh pack-full
```

O modo `collect-full` solicita confirmação **manual** antes de cada uma das 1000 capturas. É demorado. Não automatize apenas o processo `rtl_sdr`.

## 4. Avaliação NIST

`ea_restart -n <file_name> 8 <H_I>` usa `H_I` da avaliação inicial **não-IID** para a mesma configuração de fonte, com justificativa experimental. Os valores I e Q são solicitados separadamente pelo script.

```bash
bash instalar_e_executar_virgo_rng_v14.sh evaluate-full
```

O script solicita confirmação explícita dos ciclos físicos e os dois valores H_I. Não executa o teste em uma campanha de apenas 3 reinicializações. Os relatórios preservam a saída completa da ferramenta oficial; **retorno de processo zero não significa aprovação dos testes**.

## Limitações

- Dados capturados após o início do processo `rtl_sdr` podem não corresponder às primeiras amostras efetivamente geradas pelo hardware. Essa latência precisa ser caracterizada.
- `H_I` da gravação inicial não é uma garantia física; documente sua origem e condições de coleta.
- O teste de reinicialização não substitui caracterização da fonte, testes de saúde, nem avaliação do condicionamento.
- Não somar automaticamente entropias I e Q.

## v1.5 integrity audit

Run `virgo-rng restart-audit results/restart_trial --report results/restart_trial/audit.json` after packing a trial. For a full campaign, add `--require-full`. Integrity checks cannot establish whether a USB device was actually power-cycled or whether driver startup discarded initial samples.

**v1.4 bug corrected:** `restart-evaluate` now passes the separate H_I/H_Q arguments correctly; do not evaluate with v1.4.
