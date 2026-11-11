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
  echo 'Instalação concluída. Leia README_STARTUP.md e README_V18.md.'
  ;;
temporal-dipole|temporal-load|temporal-analyze|startup-trial|startup-analyze|startup-dipole|startup-load|trial|pack-trial|audit-trial|collect-full|pack-full|audit-full|evaluate-full)
  test -f .venv/bin/activate || { echo 'Execute install primeiro.' >&2; exit 2; }
  . .venv/bin/activate
  case "$MODE" in
  temporal-dipole|temporal-load)
    OUT="${2:-results/${MODE}_$(date -u +%Y%m%dT%H%M%SZ)}"
    if [[ "$MODE" == temporal-load ]]; then
      echo 'Desligue bias tee; use terminador 50 ohms RF adequado, seguro para qualquer DC residual.'
      read -r -p 'Confirmou cadeia RF e terminador adequados? [sim/N] ' ACK
      [[ "$ACK" == sim ]] || exit 0
      SETUP=50ohm-termination
    else
      SETUP=indoor-dipole
    fi
    SECONDS="${3:-180}"
    echo "Captura contínua de $SECONDS s, sem reinicializações USB. Espaço estimado: $((SECONDS*4800000/1000000)) MB."
    virgo-rng temporal-capture --out-dir "$OUT" --seconds "$SECONDS" --window-seconds 1 --setup "$SETUP"
    echo "Envie: $OUT/temporal_report.json e $OUT/capture_metadata.json"
    ;;
  temporal-analyze)
    test -n "${2:-}" || { echo 'Uso: temporal-analyze ARQUIVO.cu8 [DIR]' >&2; exit 2; }
    virgo-rng temporal-analyze "$2" --out-dir "${3:-results/temporal_offline_$(date -u +%Y%m%dT%H%M%SZ)}"
    ;;
  startup-trial)
    OUT="${2:-results/startup_$(date -u +%Y%m%dT%H%M%SZ)}"
    test ! -e "$OUT" || { echo "A pasta $OUT já existe." >&2; exit 2; }
    echo 'Desconecte fisicamente a alimentação USB, aguarde >=5 s, reconecte, só então digite RESET.'
    virgo-rng startup-collect --out-dir "$OUT" --runs 3 --pairs 262144 --block-pairs 4096 --setup indoor-dipole
    echo "Relatório: $OUT/startup_report.json"
    ;;
  startup-dipole|startup-load)
    OUT="${2:-results/${MODE}_$(date -u +%Y%m%dT%H%M%SZ)}"
    test ! -e "$OUT" || { echo "A pasta $OUT já existe." >&2; exit 2; }
    if [[ "$MODE" == startup-load ]]; then
      echo 'Use somente terminador RF 50 ohms adequado, no conector da entrada SDR. Não use curto-circuito.'
      read -r -p 'Terminador de 50 ohms conectado, com cadeia RF documentada? [sim/N] ' ACK
      [[ "$ACK" == sim ]] || exit 0
      SETUP=50ohm-termination
    else
      SETUP=indoor-dipole
    fi
    echo 'Faça 20 ciclos físicos: desconecte USB, aguarde >=5 s, reconecte e digite RESET.'
    virgo-rng startup-collect --out-dir "$OUT" --runs 20 --pairs 262144 --block-pairs 4096 --setup "$SETUP"
    echo "Relatório: $OUT/startup_report.json"
    ;;
  startup-analyze)
    test -n "${2:-}" || { echo 'Uso: startup-analyze DIRETORIO' >&2; exit 2; }
    virgo-rng startup-analyze "$2"
    ;;
  trial)
    test ! -e results/restart_trial || { echo 'A pasta results/restart_trial já existe.' >&2; exit 2; }
    virgo-rng restart-collect --out-dir results/restart_trial --runs 3 --samples 1000 --manual --setup indoor-dipole
    ;;
  pack-trial) virgo-rng restart-pack results/restart_trial ;;
  audit-trial) virgo-rng restart-audit results/restart_trial --report results/restart_trial/audit.json ;;
  collect-full)
    test ! -e results/restart_full || { echo 'A pasta results/restart_full já existe.' >&2; exit 2; }
    read -r -p 'Confirma 1000 ciclos físicos reais? [sim/N] ' ACK
    [[ "$ACK" == sim ]] || exit 0
    virgo-rng restart-collect --out-dir results/restart_full --runs 1000 --samples 1000 --manual --setup indoor-dipole
    ;;
  pack-full) virgo-rng restart-pack results/restart_full ;;
  audit-full) virgo-rng restart-audit results/restart_full --require-full --report results/restart_full/audit.json ;;
  evaluate-full)
    virgo-rng restart-audit results/restart_full --require-full --report results/restart_full/audit.json
    read -r -p 'Confirma 1000 ciclos físicos independentes? [sim/N] ' ACK
    [[ "$ACK" == sim ]] || exit 0
    read -r -p 'H_I componente I: ' HI
    read -r -p 'H_I componente Q: ' HQ
    virgo-rng restart-evaluate results/restart_full --binary "$HERE/SP800-90B_EntropyAssessment/cpp/ea_restart" --h-i "$HI" --h-q "$HQ" --ack-physical-restarts
    ;;
  esac
  ;;
*)
  echo "Uso: bash $(basename "$0") [install|temporal-dipole [DIR] [SEGUNDOS]|temporal-load [DIR] [SEGUNDOS]|temporal-analyze ARQUIVO [DIR]|startup-trial [DIR]|startup-analyze DIR|startup-dipole [DIR]|startup-load [DIR]|trial|pack-trial|audit-trial|collect-full|pack-full|audit-full|evaluate-full]"
  ;;
esac
