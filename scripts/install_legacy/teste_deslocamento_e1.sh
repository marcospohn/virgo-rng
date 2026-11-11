#!/usr/bin/env bash
set -Eeuo pipefail
# Diagnostico de pico fixo em RF versus artefato fixo em offset da sintonia.
# Uso: bash teste_deslocamento_e1.sh [diretorio_saida]
OUT="${1:-results/E1_deslocamento}"
RATE=2400000
GAIN=30
SECONDS=60
SAMPLES=$((RATE*SECONDS))
mkdir -p "$OUT"
command -v rtl_sdr >/dev/null || { echo 'ERRO: rtl_sdr nao encontrado (brew install rtl-sdr)' >&2; exit 1; }
for FREQ in 1420105752 1420405752 1420705752; do
  FILE="$OUT/centro_${FREQ}.cu8"
  echo "Captura $FREQ Hz -> $FILE"
  echo 'Mantenha antena e apontamento fixos. Pressione Enter para iniciar.'
  read -r _ </dev/tty
  START=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  rtl_sdr -f "$FREQ" -s "$RATE" -g "$GAIN" -n "$SAMPLES" "$FILE"
  END=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  BYTES=$(stat -f%z "$FILE")
  EXPECTED=$((2*SAMPLES))
  if [ "$BYTES" -ne "$EXPECTED" ]; then echo "ERRO: tamanho $BYTES, esperado $EXPECTED" >&2; exit 1; fi
  printf '%s,%s,%s,%s,%s,%s\n' "$FREQ" "$START" "$END" "$RATE" "$GAIN" "$BYTES" >> "$OUT/metadata.csv"
done
echo "Concluido: $OUT"
