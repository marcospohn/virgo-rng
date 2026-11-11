#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "Falha na linha $LINENO (código $?)." >&2' ERR
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
MODE="${1:-help}"
case "$MODE" in
persistence-iq)
  [[ $# -ge 3 ]] || { echo 'Uso: persistence-iq ARQUIVO.cu8 DIRETORIO [JANELAS] [PARES]' >&2; exit 2; }
  test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
  test -f .venv/bin/activate || { echo 'Execute install primeiro.' >&2; exit 2; }
  . .venv/bin/activate
  python -m virgo_rng.persistence121 "$2" --out-dir "$3" --windows "${4:-120}" --pairs "${5:-65536}"
  ;;
spectral-iq)
  [[ $# -ge 3 ]] || { echo 'Uso: persistence-iq ARQUIVO.cu8 DIR [JANELAS] [PARES]|spectral-iq ARQUIVO.cu8 DIRETORIO [JANELAS] [PARES_POR_JANELA]' >&2; exit 2; }
  test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
  test -f .venv/bin/activate || { echo 'Execute install primeiro.' >&2; exit 2; }
  . .venv/bin/activate
  python -m virgo_rng.spectral120 "$2" --out-dir "$3" --windows "${4:-12}" --pairs "${5:-262144}"
  ;;
local-audit)
  [[ $# -ge 3 ]] || { echo 'Uso: local-audit ARQUIVO.cu8 DIRETORIO [PERMUTACOES] [BLOCO_PARES]' >&2; exit 2; }
  test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
  test -f .venv/bin/activate || { echo 'Execute install primeiro.' >&2; exit 2; }
  . .venv/bin/activate
  python -m virgo_rng.audit119 "$2" --out-dir "$3" --permutations "${4:-199}" --block-pairs "${5:-256}"
  ;;
null-audit)
  [[ $# -ge 3 ]] || { echo 'Uso: local-audit ARQUIVO.cu8 DIRETORIO [PERMUTACOES] [BLOCO_PARES]|null-audit ARQUIVO.cu8 DIRETORIO [PERMUTACOES]' >&2; exit 2; }
  test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
  test -f .venv/bin/activate || { echo 'Execute install primeiro.' >&2; exit 2; }
  . .venv/bin/activate
  python -m virgo_rng.audit118 "$2" --out-dir "$3" --permutations "${4:-199}"
  ;;
audit-lags)
  [[ $# -ge 3 ]] || { echo 'Uso: audit-lags PRIMEIRO.json SEGUNDO.json [SAIDA.json]' >&2; exit 2; }
  python3 -m virgo_rng.audit117 "$2" "$3" --out "${4:-results/audit117/audit_report.json}"
  ;;
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
  echo 'Instalação concluída. Leia README_STARTUP.md e README_V121.md.'
  ;;
global-lag-mi|lag-mi|cross-channel|nist-screen|nist-prepare|joint-predictive|predictive-dependence|temporal-dependence|iq-dependence|temporal-dipole|temporal-load|temporal-analyze|startup-trial|startup-analyze|startup-dipole|startup-load|trial|pack-trial|audit-trial|collect-full|pack-full|audit-full|evaluate-full)
  test -f .venv/bin/activate || { echo 'Execute install primeiro.' >&2; exit 2; }
  . .venv/bin/activate
  case "$MODE" in
  nist-screen|nist-prepare)
    test -n "${2:-}" || { echo "Uso: $MODE ARQUIVO.cu8 [DIR]" >&2; exit 2; }
    test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
    OUT="${3:-results/nist_screen_$(date -u +%Y%m%dT%H%M%SZ)}"
    if [[ "$MODE" == nist-screen ]]; then
      virgo-rng nist-screen "$2" --out-dir "$OUT" --setup indoor-dipole --binary "$HERE/SP800-90B_EntropyAssessment/cpp/ea_non_iid"
      echo "Resumo: $OUT/screen_summary.json"
    else
      virgo-rng nist-screen "$2" --out-dir "$OUT" --setup indoor-dipole
      echo "Preparado: $OUT/manifest.json"
    fi
    ;;
  global-lag-mi)
    test -n "${2:-}" || { echo 'Uso: global-lag-mi ARQUIVO.cu8 [DIR] [PERMUTACOES]' >&2; exit 2; }
    test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
    virgo-rng global-lag-mi "$2" --out-dir "${3:-results/global_lag_mi_$(date -u +%Y%m%dT%H%M%SZ)}" --permutations "${4:-199}"
    ;;
  lag-mi)
    test -n "${2:-}" || { echo 'Uso: lag-mi ARQUIVO.cu8 [DIR]' >&2; exit 2; }
    test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
    virgo-rng lag-mi "$2" --out-dir "${3:-results/lag_mi_$(date -u +%Y%m%dT%H%M%SZ)}"
    ;;
  cross-channel)
    test -n "${2:-}" || { echo 'Uso: cross-channel ARQUIVO.cu8 [DIR]' >&2; exit 2; }
    test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
    virgo-rng cross-channel "$2" --out-dir "${3:-results/cross_channel_$(date -u +%Y%m%dT%H%M%SZ)}"
    ;;
  joint-predictive)
    test -n "${2:-}" || { echo 'Uso: joint-predictive ARQUIVO.cu8 [DIR]' >&2; exit 2; }
    test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
    virgo-rng joint-predictive "$2" --out-dir "${3:-results/joint_predictive_$(date -u +%Y%m%dT%H%M%SZ)}"
    ;;
  predictive-dependence)
    test -n "${2:-}" || { echo 'Uso: predictive-dependence ARQUIVO.cu8 [DIR]' >&2; exit 2; }
    test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
    virgo-rng predictive-dependence "$2" --out-dir "${3:-results/predictive_$(date -u +%Y%m%dT%H%M%SZ)}"
    ;;
  temporal-dependence)
    test -n "${2:-}" || { echo 'Uso: temporal-dependence ARQUIVO.cu8 [DIR]' >&2; exit 2; }
    test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
    virgo-rng temporal-dependence "$2" --out-dir "${3:-results/temporal_dependence_$(date -u +%Y%m%dT%H%M%SZ)}"
    ;;
  iq-dependence)
    test -n "${2:-}" || { echo 'Uso: iq-dependence ARQUIVO.cu8 [DIR]' >&2; exit 2; }
    test -f "$2" || { echo "Arquivo inexistente: $2" >&2; exit 2; }
    virgo-rng iq-dependence "$2" --out-dir "${3:-results/iq_dependence_$(date -u +%Y%m%dT%H%M%SZ)}"
    ;;
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
  echo "Uso: bash $(basename "$0") [install|audit-lags PRIMEIRO.json SEGUNDO.json [SAIDA.json]|global-lag-mi ARQUIVO.cu8 [DIR] [PERMUTACOES]|lag-mi ARQUIVO.cu8 [DIR]|nist-screen ARQUIVO.cu8 [DIR]|nist-prepare ARQUIVO.cu8 [DIR]|joint-predictive ARQUIVO.cu8 [DIR]|predictive-dependence ARQUIVO.cu8 [DIR]|temporal-dependence ARQUIVO.cu8 [DIR]|iq-dependence ARQUIVO.cu8 [DIR]|temporal-dipole [DIR] [SEGUNDOS]|temporal-load [DIR] [SEGUNDOS]|temporal-analyze ARQUIVO [DIR]|startup-trial [DIR]|startup-analyze DIR|startup-dipole [DIR]|startup-load [DIR]|trial|pack-trial|audit-trial|collect-full|pack-full|audit-full|evaluate-full]"
  ;;
esac
