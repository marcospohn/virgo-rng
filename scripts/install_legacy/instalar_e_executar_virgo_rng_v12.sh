#!/usr/bin/env bash
# Virgo-RNG v1.2 — instalação Ubuntu + campanha oficial NIST SP 800-90B
set -Eeuo pipefail
trap 'echo "ERRO na linha $LINENO (código $?). Veja a mensagem acima." >&2' ERR

ZIP="${1:-virgo_rng_v12.zip}"
if [[ ! -f "$ZIP" ]]; then echo "Arquivo ZIP não encontrado: $ZIP" >&2; echo "Uso: bash $0 /caminho/virgo_rng_v12.zip" >&2; exit 2; fi
ZIP="$(realpath "$ZIP")"
BASE="${VIRGO_WORKDIR:-$(pwd)}"
mkdir -p "$BASE"
cd "$BASE"

printf '\n== 1/8: dependências Ubuntu ==\n'
if ! command -v apt-get >/dev/null; then echo 'Este script requer Ubuntu/Debian (apt-get).' >&2; exit 2; fi
sudo apt-get update
sudo apt-get install -y git build-essential python3 python3-venv python3-pip unzip ca-certificates \
  libbz2-dev libdivsufsort-dev libjsoncpp-dev libssl-dev libmpfr-dev libgmp-dev

printf '\n== 2/8: descompactação ==\n'
if [[ -e virgo_rng_v12/pyproject.toml ]]; then
  echo 'Diretório virgo_rng_v12 já existe; preservando seus arquivos.'
else
  unzip -q "$ZIP"
fi
cd virgo_rng_v12
ROOT="$(pwd)"

printf '\n== 3/8: ambiente Python e testes ==\n'
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test,plot]'
python -m pytest -q

printf '\n== 4/8: código oficial NIST ==\n'
if [[ ! -d SP800-90B_EntropyAssessment/.git ]]; then
  git clone https://github.com/usnistgov/SP800-90B_EntropyAssessment.git
fi
NIST_DIR="$ROOT/SP800-90B_EntropyAssessment"
printf 'Revisão NIST: '
git -C "$NIST_DIR" rev-parse HEAD
(
  cd "$NIST_DIR/cpp"
  make non_iid
  make iid
)
NIST_BIN="$NIST_DIR/cpp/ea_non_iid"
if [[ ! -x "$NIST_BIN" ]]; then echo "Executável NIST ausente: $NIST_BIN" >&2; exit 1; fi

printf '\n== 5/8: preparar dados originais ==\n'
I_FILE="$ROOT/reference_results/nist/i_symbols.bin"
Q_FILE="$ROOT/reference_results/nist/q_symbols.bin"
RAW="$ROOT/antenna_01_sample.cu8"
if [[ ! -f "$RAW" ]]; then
  echo 'Reconstruindo arquivo CU8 a partir de I e Q incluídos no ZIP...'
  python - "$I_FILE" "$Q_FILE" "$RAW" <<'PY'
import hashlib, pathlib, sys
ip, qp, op = map(pathlib.Path, sys.argv[1:])
if not ip.is_file() or not qp.is_file():
    raise SystemExit('Arquivos I/Q ausentes no ZIP; forneça antenna_01_sample.cu8 no projeto.')
if ip.stat().st_size != qp.stat().st_size:
    raise SystemExit('Tamanhos I e Q incompatíveis')
with ip.open('rb') as fi, qp.open('rb') as fq, op.open('wb') as fo:
    while True:
        a, b = fi.read(1 << 20), fq.read(1 << 20)
        if not a and not b: break
        if len(a) != len(b): raise SystemExit('Blocos I/Q incompatíveis')
        interleaved = bytearray(2 * len(a))
        interleaved[0::2] = a
        interleaved[1::2] = b
        fo.write(interleaved)
print('CU8 reconstruído:', op, op.stat().st_size, 'bytes')
PY
fi
# Hash conhecido do arquivo original usado na preparação da v1.2.
EXPECTED_SHA256='a5dfd13dc1eaa963a62494405d22faa726657fd0be4c713b13528d2a0f5f33b9'
ACTUAL_SHA256="$(sha256sum "$RAW" | awk '{print $1}')"
if [[ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]]; then
  echo 'ERRO: SHA-256 do CU8 difere do arquivo de referência. Não executar campanha.' >&2
  echo "Esperado: $EXPECTED_SHA256" >&2
  echo "Obtido:   $ACTUAL_SHA256" >&2
  exit 1
fi
echo "SHA-256 confirmado: $ACTUAL_SHA256"

printf '\n== 6/8: referências anteriores (opcionais) ==\n'
REFERENCES=()
# Relatórios anteriores são opcionais: podem ser copiados para a pasta do projeto.
if [[ -f "$ROOT/i_non_iid.json" && -f "$ROOT/q_non_iid.json" ]]; then
  REFERENCES=(--reference-i "$ROOT/i_non_iid.json" --reference-q "$ROOT/q_non_iid.json")
  echo 'Relatórios I e Q encontrados; serão incluídos como referências.'
else
  echo 'Relatórios i_non_iid.json e q_non_iid.json não encontrados; campanha seguirá sem referências históricas.'
fi

printf '\n== 7/8: executar 7 avaliações oficiais NIST ==\n'
OUT="$ROOT/results/campaign12"
mkdir -p "$OUT"
virgo-rng nist-campaign "$RAW" \
  --out-dir "$OUT" \
  --pairs-per-segment 1000000 \
  --setup indoor-dipole \
  "${REFERENCES[@]}" \
  --binary "$NIST_BIN" \
  --timeout 3600

printf '\n== 8/8: consolidar e verificar resultados ==\n'
virgo-rng nist-campaign-summary "$OUT" --out "$OUT/summary.json"
python - "$OUT/summary.json" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]); report=json.loads(p.read_text())
rows=report['results']
print('\nID                         STATUS        H_FINAL    HASH OK')
print('-'*66)
for r in rows:
    h=(r.get('estimates') or {}).get('h_final')
    print(f"{r['id']:<26} {str(r['status']):<13} {str(h):<10} {r['input_hash_matches']}")
failed=[r for r in rows if r.get('status') != 'completed' or r.get('input_hash_matches') is not True or (r.get('estimates') or {}).get('h_final') is None]
if len(rows) != 7 or failed:
    raise SystemExit(f'Campanha incompleta: {len(failed)} resultado(s) inválido(s), {len(rows)} registros.')
print('\nCampanha concluída com 7 resultados íntegros.')
PY
printf '\nPRONTO!\nRelatório principal: %s\nRelatórios individuais: %s/*_non_iid.json\n' "$OUT/summary.json" "$OUT"
echo 'Envie summary.json e os sete *_non_iid.json para análise.'
