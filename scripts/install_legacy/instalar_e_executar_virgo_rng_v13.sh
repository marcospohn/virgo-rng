#!/usr/bin/env bash
# Virgo-RNG v1.3 — Ubuntu installer + NIST build + optional physical restart trial.
set -Eeuo pipefail
trap 'echo "Falha na linha $LINENO (código $?)." >&2' ERR
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-install}"
if [[ "$MODE" != install && "$MODE" != trial && "$MODE" != pack ]]; then
  echo 'Uso: bash instalar_e_executar_virgo_rng_v13.sh [install|trial|pack]' >&2
  exit 2
fi
cd "$HERE"
if [[ ! -f pyproject.toml ]]; then echo 'Execute o script dentro da pasta virgo_rng_v13.' >&2; exit 2; fi
if [[ "$MODE" == install ]]; then
  echo '== Dependências Ubuntu =='
  command -v apt-get >/dev/null || { echo 'Requer Ubuntu/Debian.' >&2; exit 2; }
  sudo apt-get update
  sudo apt-get install -y git build-essential python3 python3-venv python3-pip unzip \
    rtl-sdr libusb-1.0-0-dev libbz2-dev libdivsufsort-dev libjsoncpp-dev \
    libssl-dev libmpfr-dev libgmp-dev ca-certificates
  echo '== Ambiente Python =='
  python3 -m venv .venv
  . .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -e '.[test,plot]'
  python -m pytest -q
  echo '== Implementação de referência NIST SP 800-90B =='
  if [[ ! -d SP800-90B_EntropyAssessment/.git ]]; then
    git clone https://github.com/usnistgov/SP800-90B_EntropyAssessment.git
  fi
  git -C SP800-90B_EntropyAssessment rev-parse HEAD | tee nist_git_commit.txt
  (cd SP800-90B_EntropyAssessment/cpp && make non_iid && make iid)
  echo '== Verificações =='
  test -x SP800-90B_EntropyAssessment/cpp/ea_non_iid
  command -v rtl_sdr
  echo 'Instalação concluída. Para um teste com 3 reinicializações FÍSICAS:'
  echo '  bash instalar_e_executar_virgo_rng_v13.sh trial'
  echo 'A coleta NÃO é iniciada automaticamente.'
  exit 0
fi
if [[ ! -f .venv/bin/activate ]]; then echo 'Execute primeiro o modo install.' >&2; exit 2; fi
. .venv/bin/activate
OUT="$HERE/results/restart_trial"
if [[ "$MODE" == trial ]]; then
  echo 'ATENÇÃO: cada rodada exige desligar e religar FISICAMENTE o RTL-SDR.'
  echo 'Reiniciar somente o processo rtl_sdr não satisfaz essa condição.'
  echo 'Não use --manual sem realizar os ciclos físicos de alimentação.'
  if [[ -e "$OUT" ]]; then
    echo "A pasta $OUT já existe. Preserve-a ou mova-a antes de novo ensaio." >&2
    exit 2
  fi
  read -r -p 'Confirma que poderá fazer 3 reinicializações físicas? [sim/N] ' ACK
  [[ "$ACK" == sim ]] || { echo 'Cancelado.'; exit 0; }
  virgo-rng restart-collect --out-dir "$OUT" --runs 3 --samples 1000 --manual --setup indoor-dipole
  echo "Capturas concluídas em: $OUT"
  echo 'Para empacotar: bash instalar_e_executar_virgo_rng_v13.sh pack'
elif [[ "$MODE" == pack ]]; then
  [[ -d "$OUT" ]] || { echo "Pasta não encontrada: $OUT" >&2; exit 2; }
  virgo-rng restart-pack "$OUT"
  echo "Matrizes de teste em: $OUT"
  echo 'Este ensaio de 3 rodadas NÃO é o teste NIST de 1000 reinicializações.'
fi
