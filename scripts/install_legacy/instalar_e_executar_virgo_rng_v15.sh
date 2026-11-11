#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "Falha na linha $LINENO (código $?)." >&2' ERR
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
MODE="${1:-help}"
case "$MODE" in
install)
  sudo apt-get update
  sudo apt-get install -y git build-essential python3 python3-venv python3-pip rtl-sdr libusb-1.0-0-dev libbz2-dev libdivsufsort-dev libjsoncpp-dev libssl-dev libmpfr-dev libgmp-dev ca-certificates
  python3 -m venv .venv
  . .venv/bin/activate
  python -m pip install -e '.[test,plot]'
  python -m pytest -q
  if [[ ! -d SP800-90B_EntropyAssessment/.git ]]; then
    git clone https://github.com/usnistgov/SP800-90B_EntropyAssessment.git
  fi
  git -C SP800-90B_EntropyAssessment rev-parse HEAD | tee nist_git_commit.txt
  (cd SP800-90B_EntropyAssessment/cpp && make non_iid && make iid && make restart)
  test -x SP800-90B_EntropyAssessment/cpp/ea_restart
  echo 'Instalação concluída. Leia README_RESTART.md.'
  ;;
trial|pack-trial|audit-trial|collect-full|pack-full|audit-full|evaluate-full)
  test -f .venv/bin/activate || { echo 'Execute install primeiro.' >&2; exit 2; }
  . .venv/bin/activate
  case "$MODE" in
  trial)
    test ! -e results/restart_trial || { echo 'A pasta results/restart_trial já existe.' >&2; exit 2; }
    virgo-rng restart-collect --out-dir results/restart_trial --runs 3 --samples 1000 --manual --setup indoor-dipole
    ;;
  pack-trial) virgo-rng restart-pack results/restart_trial ;;
  audit-trial) virgo-rng restart-audit results/restart_trial --report results/restart_trial/audit.json ;;
  collect-full)
    test ! -e results/restart_full || { echo 'A pasta results/restart_full já existe.' >&2; exit 2; }
    echo 'ATENÇÃO: 1000 ciclos físicos reais; não apenas reiniciar rtl_sdr.'
    read -r -p 'Confirma a execução manual de 1000 ciclos físicos? [sim/N] ' ACK
    [[ "$ACK" == sim ]] || exit 0
    virgo-rng restart-collect --out-dir results/restart_full --runs 1000 --samples 1000 --manual --setup indoor-dipole
    ;;
  pack-full) virgo-rng restart-pack results/restart_full ;;
  audit-full) virgo-rng restart-audit results/restart_full --require-full --report results/restart_full/audit.json ;;
  evaluate-full)
    virgo-rng restart-audit results/restart_full --require-full --report results/restart_full/audit.json
    read -r -p 'Confirma que ocorreram 1000 ciclos FÍSICOS independentes? [sim/N] ' ACK
    [[ "$ACK" == sim ]] || exit 0
    read -r -p 'H_I para componente I (bits/amostra, não-IID): ' HI
    read -r -p 'H_I para componente Q (bits/amostra, não-IID): ' HQ
    BIN="$HERE/SP800-90B_EntropyAssessment/cpp/ea_restart"
    virgo-rng restart-evaluate results/restart_full --binary "$BIN" --h-i "$HI" --h-q "$HQ" --ack-physical-restarts
    ;;
  esac
  ;;
*) echo "Uso: bash $(basename "$0") [install|trial|pack-trial|audit-trial|collect-full|pack-full|audit-full|evaluate-full]" ;;
esac
