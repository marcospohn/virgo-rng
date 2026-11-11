#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
MODE="${1:-help}"
case "$MODE" in
  install)
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip rtl-sdr git build-essential
    python3 -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -e '.[plot,test]'
    .venv/bin/python -m pytest -q
    echo 'Instalado. Para hardware, confira rtl_test -t e regras udev do RTL-SDR.'
    ;;
  test)
    .venv/bin/python -m pytest -q ;;
  init)
    .venv/bin/virgo-rng-lab init --out "${2:-virgo_config.json}" ;;
  study)
    [[ $# -ge 3 ]] || { echo 'Uso: study ARQUIVO.cu8 DIR_SAIDA [CONFIG.json]' >&2; exit 2; }
    args=(study "$2" --out-dir "$3")
    [[ $# -lt 4 ]] || args+=(--config "$4")
    .venv/bin/virgo-rng-lab "${args[@]}" ;;
  study-full)
    [[ $# -ge 3 ]] || { echo 'Uso: study-full ARQUIVO.cu8 DIR_SAIDA [CONFIG.json]' >&2; exit 2; }
    args=(study "$2" --out-dir "$3" --full)
    [[ $# -lt 4 ]] || args+=(--config "$4")
    .venv/bin/virgo-rng-lab "${args[@]}" ;;
  capture)
    [[ $# -ge 4 ]] || { echo 'Uso: capture ARQUIVO.cu8 RELATORIO.json SEGUNDOS [CONFIG.json]' >&2; exit 2; }
    args=(capture --out "$2" --report "$3" --seconds "$4")
    [[ $# -lt 5 ]] || args+=(--config "$5")
    .venv/bin/virgo-rng-lab "${args[@]}" ;;
  legacy)
    shift; .venv/bin/virgo-rng "$@" ;;
  nist-install)
    sudo apt-get install -y git make g++ libbz2-dev libdivsufsort-dev libjsoncpp-dev libssl-dev libmpfr-dev libgmp-dev
    if [[ ! -d SP800-90B_EntropyAssessment/.git ]]; then git clone https://github.com/usnistgov/SP800-90B_EntropyAssessment.git; fi
    git -C SP800-90B_EntropyAssessment rev-parse HEAD | tee nist_git_commit.txt
    (cd SP800-90B_EntropyAssessment/cpp && make non_iid && make iid && make restart)
    echo 'Ferramentas NIST instaladas; resultados NÃO implicam certificação.' ;;
  help|*)
    cat <<'EOF'
Virgo-RNG 2.0 — Ubuntu
  bash instalar_e_executar_virgo_rng_v2.sh install
  bash instalar_e_executar_virgo_rng_v2.sh init
  bash instalar_e_executar_virgo_rng_v2.sh study captura.cu8 resultados/estudo
  bash instalar_e_executar_virgo_rng_v2.sh study-full captura.cu8 resultados/completo
  bash instalar_e_executar_virgo_rng_v2.sh capture captura.cu8 captura_report.json 180 virgo_config.json
  bash instalar_e_executar_virgo_rng_v2.sh legacy --help
  bash instalar_e_executar_virgo_rng_v2.sh nist-install
  bash instalar_e_executar_virgo_rng_v2.sh test

Atenção: geração condicionada existente é EXPERIMENTAL, não RNG criptográfico validado.
EOF
    ;;
esac
