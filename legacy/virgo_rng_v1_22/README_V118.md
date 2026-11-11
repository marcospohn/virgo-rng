# Virgo-RNG v1.18 — auditoria dos controles temporais

Esta versão compara **duas faixas de deslocamento circular** de Q (`wide` e `half_turn`), preserva **todas as curvas nulas** em `null_profiles.npz` e registra médias/desvios por janela e MI em ±8.

## Ubuntu

```bash
unzip virgo_rng_v118.zip
cd virgo_rng_v118
bash instalar_e_executar_virgo_rng_v118.sh install
bash instalar_e_executar_virgo_rng_v118.sh null-audit /CAMINHO/PRIMEIRA/continuous.cu8 results/audit_primeira 199
bash instalar_e_executar_virgo_rng_v118.sh null-audit /CAMINHO/SEGUNDA/continuous.cu8 results/audit_segunda 199
```

Saídas por captura: `null_audit_report.json`, `null_profiles.npz`, `null_audit_plot.png`.

**Limitações:** ambos os controles ainda são deslocamentos circulares, de modo que a comparação é somente um teste de sensibilidade, não uma validação da hipótese nula. O arquivo NPZ preserva os perfis e offsets, permitindo auditoria independente. A análise não mede min-entropia criptográfica. Resultados da primeira captura continuam exploratórios. O script `install` requer internet e compila as ferramentas NIST; testes de software não equivalem a testes com o SDR físico.
