# Virgo-RNG v1.21 — persistência temporal I/Q

Esta versão adiciona `persistence-iq` para medir a autocorrelação I/Q em lag 1 e a correlação cruzada em ±8 e ±41 separadamente em janelas ao longo de arquivos CU8. Também produz a componente antissimétrica `[corr(+k)-corr(-k)]/2`.

## Instalação Ubuntu

```bash
unzip virgo_rng_v121.zip
cd virgo_rng_v121
bash instalar_e_executar_virgo_rng_v121.sh install
```

## Análise das duas capturas (caminhos ajustáveis)

```bash
bash instalar_e_executar_virgo_rng_v121.sh persistence-iq ../continuous-primeira.cu8 results/persistence_primeira 120 65536
bash instalar_e_executar_virgo_rng_v121.sh persistence-iq ../continuous-segunda.cu8 results/persistence_segunda 120 65536
```

Arquivos de saída: `persistence_report.json` e `persistence_plot.png`. Envie ambos os JSONs para comparação.

**Atenção:** os 120 segmentos são amostrados espaçadamente; a cobertura é de ~1,82% de cada arquivo de 864 MB. Resultados são descritivos, não testes estatísticos calibrados e não estimam min-entropia. A persistência não demonstra origem astronômica. Para o controle de 50 Ω, desabilite bias tee antes de conectar uma carga que não suporte DC.
