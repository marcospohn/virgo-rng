#!/usr/bin/env bash
set -Eeuo pipefail

# Instalador NIST SP 800-90B para macOS Apple Silicon e Intel
VERSION="${NIST_VERSION:-v1.1.8}"
ROOT="${NIST_ROOT:-$HOME/astronomia/tools/nist-sp800-90b}"
PREFIX="${NIST_PREFIX:-$HOME/.local}"
REPO="https://github.com/usnistgov/SP800-90B_EntropyAssessment.git"

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }
trap 'echo "Falha na linha $LINENO; examine a mensagem acima." >&2' ERR

[[ "$(uname -s)" == "Darwin" ]] || die "Este script exige macOS."
if ! xcode-select -p >/dev/null 2>&1; then
    xcode-select --install || true
    die "Conclua a instalacao das ferramentas Xcode e execute novamente."
fi

for location in /opt/homebrew/bin /usr/local/bin; do
    [[ -x "$location/brew" ]] && export PATH="$location:$PATH"
done
command -v brew >/dev/null || die "Instale o Homebrew: https://brew.sh"
eval "$(brew shellenv)"

log "Instalando dependencias"
brew install gcc git jsoncpp mpfr gmp libdivsufsort openssl@3 bzip2

BP="$(brew --prefix)"
GCC="$(find "$BP/bin" -maxdepth 1 -type l -name 'g++-[0-9]*' | sort -V | tail -1)"
[[ -n "$GCC" && -x "$GCC" ]] || die "Nao encontrei o GCC do Homebrew."
log "Usando $GCC"

INC=""
LIBDIR=""
RPATH=""
for package in jsoncpp libdivsufsort openssl@3 bzip2 gmp mpfr; do
    dir="$(brew --prefix "$package")"
    INC="$INC -I$dir/include"
    LIBDIR="$LIBDIR -L$dir/lib"
    RPATH="$RPATH -Wl,-rpath,$dir/lib"
done

mkdir -p "$(dirname "$ROOT")" "$PREFIX/bin"
if [[ -d "$ROOT/.git" ]]; then
    log "Atualizando repositorio"
    git -C "$ROOT" fetch origin --tags
else
    [[ ! -e "$ROOT" ]] || die "Diretorio existente nao e repositorio: $ROOT"
    log "Baixando projeto oficial"
    git clone "$REPO" "$ROOT"
fi
git -C "$ROOT" checkout --detach "$VERSION"
log "Commit instalado: $(git -C "$ROOT" rev-parse HEAD)"
cd "$ROOT/cpp"

# O Makefile original pressupoe /usr/include/jsoncpp e flags x86.
# Sobrescrevemos esses valores sem alterar os fontes do NIST.
CXXFLAGS="-std=c++11 -fopenmp -O2 -ffloat-store $INC"
SHARED="-ljsoncpp -lcrypto $LIBDIR $RPATH"
COMMON="-lbz2 -lpthread -ldivsufsort -ldivsufsort64"

log "Compilando"
make clean
make -j 2 all ARCH=arm64 CXX="$GCC" CXXFLAGS="$CXXFLAGS" \
    LIB="$COMMON" SHARED_LIB="$SHARED" COND_LIB="-lmpfr -lgmp"

log "Executando autotestes"
if [[ -x selftest/selftest ]]; then
    (cd selftest && ./selftest)
else
    log "Autoteste automatico indisponivel; consulte cpp/selftest."
fi

log "Instalando executaveis"
for bin in ea_non_iid ea_iid ea_restart ea_conditioning ea_transpose; do
    [[ -x "$bin" ]] || die "Nao foi compilado: $bin"
    install -m 755 "$bin" "$PREFIX/bin/$bin"
done

# PATH persistente no zsh
LINE='export PATH="$HOME/.local/bin:$PATH"'
if ! grep -Fqx "$LINE" "$HOME/.zprofile" 2>/dev/null; then
    printf '\n# NIST SP 800-90B\n%s\n' "$LINE" >> "$HOME/.zprofile"
fi
export PATH="$PREFIX/bin:$PATH"

log "Instalacao finalizada"
for bin in ea_non_iid ea_iid ea_restart ea_conditioning ea_transpose; do
    command -v "$bin"
done
printf '\nUse: source ~/.zprofile\n'
printf 'Depois: ea_non_iid -i -t arquivo.bin 8\n'
