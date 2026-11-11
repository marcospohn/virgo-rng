#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reprocessamento espectral integral E7 a partir dos CU8 originais.

Requisitos: Python 3.9+, numpy; matplotlib opcional para PNGs.
Nao acessa hardware nem altera CU8, metadata.json ou resultados anteriores.

Exemplo:
    python virgo_e7_reprocessar_dc.py --dir results/E7_carina

Saida: results/E7_carina/analysis_dc/
Reexecute o mesmo comando apos interrupcao: capturas ja processadas sao retomadas do cache.

ATENCAO CIENTIFICA:
 - DC corrigido = media COMPLEXA de cada bloco removida ANTES da janela e da FFT.
 - Excesso ON/OFF nao e identificacao definitiva de H I.
 - A janela candidata de 1420.392 MHz sobrepoe a frequencia central 1420.405752 MHz.
 - Janelas temporais nao equivalem a observacoes celestes independentes.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

NAMES = ("A1", "ON1", "OFF1", "ON2", "OFF2", "ON3", "A2")
PAIRS = (("ON1", "OFF1"), ("ON2", "OFF1"), ("ON2", "OFF2"), ("ON3", "OFF2"))
DEFAULT_CENTER = 1_420_405_752
DEFAULT_RATE = 2_400_000
DEFAULT_TARGET = 1_420_392_000
VERSION = "1.0.0"


def atomic_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False)
    os.replace(tmp, path)


def moving_mean(x: np.ndarray, width: int) -> np.ndarray:
    width = int(width)
    if width < 1 or width % 2 != 1:
        raise ValueError("Largura do filtro deve ser impar e positiva")
    if width == 1:
        return x.copy()
    pad = width // 2
    return np.convolve(np.pad(x, (pad, pad), mode="reflect"),
                       np.full(width, 1.0 / width), mode="valid")


def clean_center(freq: np.ndarray, ratio_db: np.ndarray, center_hz: float,
                 mask_hz: float) -> np.ndarray:
    """Interpola bins espurios ANTES dos filtros. Usado somente em razoes dB."""
    if mask_hz <= 0:
        return ratio_db.copy()
    invalid = np.abs(freq - center_hz) <= mask_hz
    good = ~invalid
    if good.sum() < 3:
        raise ValueError("Mascara DC removeu todos os canais")
    return np.interp(freq, freq[good], ratio_db[good])


def metrics(freq: np.ndarray, power_on: np.ndarray, power_off: np.ndarray,
            center: int, target: int, half_width: float, mask_khz: float,
            smooth_bins: int, baseline_bins: int) -> dict:
    eps = 1e-24
    ratio = 10 * np.log10(np.maximum(power_on, eps) / np.maximum(power_off, eps))
    mask_hz = mask_khz * 1000
    cleaned = clean_center(freq, ratio, center, mask_hz)
    smooth = moving_mean(cleaned, smooth_bins)
    residual = smooth - moving_mean(smooth, baseline_bins)

    offset = freq - target
    band = np.abs(offset) <= half_width
    side = ((np.abs(offset) >= 2 * half_width) & (np.abs(offset) <= 4 * half_width))
    valid = np.abs(freq - center) > mask_hz if mask_hz > 0 else np.ones(len(freq), dtype=bool)
    band &= valid
    side &= valid
    if band.sum() < 5 or side.sum() < 10:
        raise ValueError("Janela de frequencia insuficiente apos mascara; reduza --masks-khz")

    # Metricas comparaveis ao pipeline E7 (filtros 35/341 com FFT=8192).
    band_med = float(np.median(residual[band]))
    side_med = float(np.median(residual[side]))
    feature = band_med - side_med

    # Medida alternativa: linha de base linear usando APENAS faixas laterais.
    # Nao suaviza/usa canal DC no ajuste nem na regiao candidata.
    x = offset / 1000.0
    coeff = np.polyfit(x[side], ratio[side], deg=1)
    linear_resid = ratio - np.polyval(coeff, x)
    alt_feature = float(np.median(linear_resid[band]))

    return {
        "mask_dc_khz": float(mask_khz),
        "band_minus_sideband_db": float(feature),
        "band_median_db": band_med,
        "sideband_median_db": side_med,
        "linear_sideband_fit_db": alt_feature,
        "n_band_bins_used": int(band.sum()),
        "n_sideband_bins_used": int(side.sum()),
    }


def process_one(path: Path, sample_rate: int, fft_size: int, window_seconds: float,
                batch_blocks: int) -> dict:
    """Le TODO o CU8 uma vez em lotes, estimando dois periodogramas por FFT.

    A correção por bloco é matematicamente equivalente a FFT((x-mean(x))*hann),
    mas usa FFT(x*hann)-mean(x)*FFT(hann), evitando computar duas FFTs.
    """
    raw = np.memmap(path, dtype=np.uint8, mode="r")
    if raw.size % 2:
        raise ValueError(f"{path}: numero impar de bytes (CU8 incompleto)")
    n_complex = int(raw.size // 2)
    fft_blocks = n_complex // fft_size
    if fft_blocks < 2:
        raise ValueError(f"{path}: menos de 2 blocos FFT")
    win = np.hanning(fft_size).astype(np.float32)
    fftwin = np.fft.fft(win)
    psd_raw = np.zeros(fft_size, np.float64)
    psd_dc = np.zeros(fft_size, np.float64)
    windows = []

    # Divisao temporal real em janelas nao sobrepostas; sobras <FFT sao descartadas.
    samples_per_window = max(fft_size, int(round(window_seconds * sample_rate)))
    n_windows = math.ceil(n_complex / samples_per_window)
    total_used = 0
    dc_sum = 0.0 + 0.0j
    dc_sum_square = 0.0

    for iw in range(n_windows):
        window_start = iw * samples_per_window
        window_end = min((iw + 1) * samples_per_window, n_complex)
        count = (window_end - window_start) // fft_size
        if count == 0:
            continue
        p_raw = np.zeros(fft_size, dtype=np.float64)
        p_dc = np.zeros(fft_size, dtype=np.float64)
        for k in range(0, count, batch_blocks):
            b = min(batch_blocks, count - k)
            start_sample = window_start + k * fft_size
            end_sample = start_sample + b * fft_size
            buf = np.asarray(raw[2 * start_sample:2 * end_sample], dtype=np.float32).reshape(b, fft_size, 2)
            # CU8: I,Q unsigned 0..255, DC level around 127.5.
            iq = (buf[:, :, 0] - 127.5) + 1j * (buf[:, :, 1] - 127.5)
            means = np.mean(iq, axis=1)
            dc_sum += np.sum(means)
            dc_sum_square += float(np.sum(np.abs(means) ** 2))
            ft = np.fft.fft(iq * win, axis=1)
            p_raw += np.sum(ft.real**2 + ft.imag**2, axis=0)
            ft -= means[:, None] * fftwin[None, :]
            p_dc += np.sum(ft.real**2 + ft.imag**2, axis=0)
            del buf, iq, ft
        psd_raw += p_raw
        psd_dc += p_dc
        total_used += count
        windows.append((window_start / sample_rate, window_end / sample_rate,
                        count, p_raw / count, p_dc / count))
        print(f"  {path.stem}: janela {iw+1}/{n_windows} ({count} FFT)", flush=True)

    if total_used == 0:
        raise ValueError(f"{path.name}: sem FFTs completas")
    # FFT shift is applied here for correct monotonic frequency axis.
    windows_raw = np.stack([np.fft.fftshift(w[3]) for w in windows])
    windows_dc = np.stack([np.fft.fftshift(w[4]) for w in windows])
    return {
        "raw": np.fft.fftshift(psd_raw / total_used),
        "dc": np.fft.fftshift(psd_dc / total_used),
        "win_raw": windows_raw,
        "win_dc": windows_dc,
        "win_start_s": np.array([w[0] for w in windows], dtype=np.float64),
        "win_end_s": np.array([w[1] for w in windows], dtype=np.float64),
        "win_blocks": np.array([w[2] for w in windows], dtype=np.int32),
        "blocks": total_used,
        "samples": n_complex,
        "unused_samples": n_complex - fft_size * total_used,
        "mean_block_dc_real": float(dc_sum.real / total_used),
        "mean_block_dc_imag": float(dc_sum.imag / total_used),
        "rms_block_dc": float(np.sqrt(dc_sum_square / total_used)),
    }


def cache_path(out: Path, name: str) -> Path:
    return out / "cache" / f"{name}_spectra.npz"


def process_cached(path: Path, out: Path, name: str, config: dict,
                   force: bool) -> dict:
    cp = cache_path(out, name)
    stamp = {"bytes": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns,
             "rate": config["rate"], "fft": config["fft"],
             "window_seconds": config["window_seconds"], "batch_blocks": config["batch_blocks"],
             "script_version": VERSION}
    if cp.is_file() and not force:
        try:
            with np.load(cp, allow_pickle=False) as z:
                stored = json.loads(str(z["stamp"].item()))
                if stored == stamp:
                    print(f"{name}: carregado do cache (captura ja processada).", flush=True)
                    return {key: z[key].copy() for key in z.files if key != "stamp"}
        except (ValueError, OSError, KeyError, json.JSONDecodeError):
            print(f"{name}: cache invalido; recalculando.", flush=True)

    print(f"{name}: lendo integralmente {path.name} ({path.stat().st_size / 1e6:.0f} MB)", flush=True)
    result = process_one(path, config["rate"], config["fft"], config["window_seconds"],
                         config["batch_blocks"])
    cp.parent.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, stamp=json.dumps(stamp), **result)
    os.replace(tmp, cp)
    print(f"{name}: cache salvo", flush=True)
    return result


def check_meta(directory: Path, names, sample_rate: int, center: int):
    mf = directory / "metadata.json"
    if not mf.is_file():
        raise ValueError(f"metadata.json nao encontrado em {directory}")
    records = json.loads(mf.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("metadata.json esperado como lista de registros")
    by = {r.get("name"): r for r in records if isinstance(r, dict)}
    for name in names:
        rec = by.get(name)
        if not rec or rec.get("status") != "complete":
            raise ValueError(f"{name} nao consta como completa no metadata.json")
        path = directory / f"{name}.cu8"
        if not path.is_file():
            raise ValueError(f"Arquivo original ausente: {path}")
        size = path.stat().st_size
        if int(rec.get("bytes", -1)) != size:
            raise ValueError(f"{name}: tamanho CU8 nao corresponde ao metadata.json: {size} bytes")
        if int(rec.get("center_hz", center)) != center:
            raise ValueError(f"{name}: frequencia central difere: {rec.get('center_hz')}")
        if int(rec.get("sample_rate_hz", sample_rate)) != sample_rate:
            raise ValueError(f"{name}: taxa de amostragem difere: {rec.get('sample_rate_hz')}")
    return by


def write_csv(path: Path, columns, values):
    with path.open("w", encoding="utf-8", newline="") as file:
        w = csv.writer(file)
        w.writerow(columns)
        w.writerows(values)


def charts(out: Path, freq: np.ndarray, spec: dict, comparisons: list,
           config: dict, rows: list):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib nao instalado: CSV/JSON gerados, graficos omitidos.")
        return
    f = freq / 1e6
    lo = config["target"] / 1e6 - 0.10
    hi = config["target"] / 1e6 + 0.10
    loc = (f >= lo) & (f <= hi)
    fig, axs = plt.subplots(2, 1, figsize=(10, 7.4), constrained_layout=True)
    for name in ("ON1", "OFF1", "ON2", "OFF2", "ON3"):
        s = spec[name]["dc"]
        # Normalizar so para forma, nao usar como calibracao de potencia.
        yy = 10*np.log10(np.maximum(s, 1e-24))
        yy -= float(np.median(yy[loc]))
        axs[0].plot(f[loc], yy[loc], linewidth=0.8, label=name)
    axs[0].axvline(config["center"]/1e6, color="k", linestyle=":", label="Centro SDR")
    axs[0].axvspan((config["target"]-config["half_width_hz"])/1e6,
                   (config["target"]+config["half_width_hz"])/1e6,
                   alpha=0.1, color="grey", label="Janela candidata")
    axs[0].set(title="Espectros apos remocao de DC por bloco (formas, sem calibracao)",
               ylabel="Potencia relativa (dB)", xlabel="Frequencia (MHz)")
    axs[0].legend(fontsize=7, ncol=4)
    axs[0].grid(alpha=.2)
    for entry in comparisons:
        if entry["method"] != "dc_removed" or entry["mask_dc_khz"] != 5.0:
            continue
        on, off = entry["on"], entry["off"]
        ratio = 10*np.log10(np.maximum(spec[on]["dc"],1e-24)/np.maximum(spec[off]["dc"],1e-24))
        cleaned = clean_center(freq, ratio, config["center"], 5000)
        sm = moving_mean(cleaned, config["smooth_bins"])
        residual = sm - moving_mean(sm, config["baseline_bins"])
        axs[1].plot(f[loc], residual[loc], linewidth=.9, label=f"{on}/{off}")
    axs[1].axhline(0, color="grey", lw=.7)
    axs[1].axvline(config["center"]/1e6, color="k", linestyle=":")
    axs[1].axvspan((config["target"]-config["half_width_hz"])/1e6,
                   (config["target"]+config["half_width_hz"])/1e6,
                   alpha=0.1, color="grey")
    axs[1].set(title="Contrastes com correcao DC e mascara central de 5 kHz",
               ylabel="Excesso residual (dB)", xlabel="Frequencia (MHz)")
    axs[1].legend(fontsize=8)
    axs[1].grid(alpha=.2)
    fig.savefig(out / "e7_dc_spectra.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.5), constrained_layout=True)
    order = {n:i for i,n in enumerate(NAMES)}
    for name in NAMES:
        subset = [r for r in rows if r["capture"] == name and
                  r["method"] == "dc_removed" and r["mask_dc_khz"] == 5.0]
        if subset:
            ax.scatter([order[name] + (r["start_s"]+r["end_s"])/
                        max(1.0, spec[name]["samples"]/config["rate"])*.7 for r in subset],
                       [r["local_feature_db"] for r in subset], s=12, label=name)
    ax.set_xticks([order[n]+.35 for n in NAMES], NAMES)
    ax.set(xlabel="Capturas, com janelas em ordem temporal", ylabel="Excesso local (dB)",
           title="E7: variabilidade por janela (nao sao observacoes independentes)")
    ax.axhline(0, color="grey", lw=.8)
    ax.grid(alpha=.2)
    fig.savefig(out / "e7_dc_windows.png", dpi=160)
    plt.close(fig)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", required=True, type=Path, help="Diretorio original: results/E7_carina")
    p.add_argument("--output", type=Path, default=None, help="Saida (padrao: --dir/analysis_dc)")
    p.add_argument("--fft", type=int, default=8192, help="Tamanho FFT, potencia de 2 (padrao 8192)")
    p.add_argument("--window-seconds", type=float, default=10.0, help="Janelas de tempo, em segundos")
    p.add_argument("--batch-blocks", type=int, default=128, help="FFTs por lote (reduzir se faltar RAM)")
    p.add_argument("--center-hz", type=int, default=DEFAULT_CENTER)
    p.add_argument("--rate", type=int, default=DEFAULT_RATE)
    p.add_argument("--target-hz", type=int, default=DEFAULT_TARGET)
    p.add_argument("--half-width-khz", type=float, default=20.)
    p.add_argument("--masks-khz", type=float, nargs="+", default=[0., 2., 5., 10.],
                   help="Mascaras do centro, em kHz (0 = nenhuma)")
    p.add_argument("--force", action="store_true", help="Ignorar caches e recalcular capturas")
    args = p.parse_args(argv)

    if args.fft < 256 or args.fft & (args.fft-1):
        p.error("--fft deve ser potencia de 2, no minimo 256")
    if args.window_seconds <= 0 or args.batch_blocks < 1 or args.rate <= 0:
        p.error("Parametros de janela, lote e amostragem devem ser positivos")
    if args.half_width_khz <= 0 or any(x < 0 for x in args.masks_khz):
        p.error("Banda e mascaras devem ser nao negativas; largura de banda >0")

    config = dict(center=args.center_hz, rate=args.rate, fft=args.fft,
                  target=args.target_hz, half_width_hz=args.half_width_khz*1000,
                  window_seconds=args.window_seconds, batch_blocks=args.batch_blocks,
                  smooth_bins=max(1, round(10_250/(args.rate/args.fft))//2*2+1),
                  baseline_bins=max(1, round(99_900/(args.rate/args.fft))//2*2+1),
                  masks_khz=sorted(set(float(x) for x in args.masks_khz)))
    directory = args.dir
    out = args.output if args.output is not None else directory / "analysis_dc"
    try:
        check_meta(directory, NAMES, args.rate, args.center_hz)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    out.mkdir(parents=True, exist_ok=True)
    freq = args.center_hz + np.fft.fftshift(np.fft.fftfreq(args.fft, 1. / args.rate))
    spec = {}
    for name in NAMES:
        spec[name] = process_cached(directory / f"{name}.cu8", out, name, config, args.force)

    spectra_names = ["frequency_hz"] + [f"{name}_{m}_power" for name in NAMES for m in ("raw", "dc")]
    write_csv(out / "individual_spectra.csv", spectra_names,
              zip(freq, *[spec[n][m] for n in NAMES for m in ("raw", "dc")]))

    comparisons = []
    for on, off in PAIRS:
        for method, col in (("before_dc", "raw"), ("dc_removed", "dc")):
            for mask in config["masks_khz"]:
                r = metrics(freq, spec[on][col], spec[off][col], args.center_hz,
                            args.target_hz, config["half_width_hz"], mask,
                            config["smooth_bins"], config["baseline_bins"])
                comparisons.append(dict(on=on, off=off, method=method, **r))

    # Controles do pico DC no centro: mede efeito da remocao por bloco no PSD.
    idx_center = int(np.argmin(np.abs(freq - args.center_hz)))
    dc_checks = {}
    for name in NAMES:
        s = spec[name]
        ratio = 10 * math.log10(max(s["dc"][idx_center], 1e-24) /
                                max(s["raw"][idx_center], 1e-24))
        dc_checks[name] = {
            "center_bin_power_change_db": ratio,
            "center_bin_before_power": float(s["raw"][idx_center]),
            "center_bin_after_power": float(s["dc"][idx_center]),
            "mean_block_dc_i": float(s["mean_block_dc_real"]),
            "mean_block_dc_q": float(s["mean_block_dc_imag"]),
            "rms_block_dc": float(s["rms_block_dc"]),
            "blocks_used": int(s["blocks"]),
            "fraction_of_samples_discarded": float(s["unused_samples"] / s["samples"]),
        }

    window_rows = []
    for name in NAMES:
        s = spec[name]
        for j in range(len(s["win_start_s"])):
            for col, method in (("raw", "before_dc"), ("dc", "dc_removed")):
                # Comparacao local com o PROPRIO espectro, nao prova astronomia.
                # Baseline via faixas laterais para cada captura/janela.
                for mask in config["masks_khz"]:
                    m = metrics(freq, s[f"win_{col}"][j],
                                np.full(args.fft, np.median(s[f"win_{col}"][j])),
                                args.center_hz, args.target_hz,
                                config["half_width_hz"], mask,
                                config["smooth_bins"], config["baseline_bins"])
                    window_rows.append({"capture": name, "start_s":float(s["win_start_s"][j]),
                                        "end_s":float(s["win_end_s"][j]), "fft_blocks":int(s["win_blocks"][j]),
                                        "method":method, "mask_dc_khz":mask,
                                        "local_feature_db":m["band_minus_sideband_db"],
                                        "linear_sideband_fit_db":m["linear_sideband_fit_db"]})

    # Paired window tests: correspondem a tempos RELATIVOS, nao horarios de cielo simultaneos.
    window_pair_rows = []
    for on, off in PAIRS:
        nso, nsf = spec[on], spec[off]
        kmax = min(len(nso["win_start_s"]), len(nsf["win_start_s"]))
        for j in range(kmax):
            for mask in config["masks_khz"]:
                m = metrics(freq, nso["win_dc"][j], nsf["win_dc"][j],
                            args.center_hz, args.target_hz,
                            config["half_width_hz"], mask,
                            config["smooth_bins"], config["baseline_bins"])
                window_pair_rows.append(dict(on=on, off=off, window_index=j,
                    on_start_s=float(nso["win_start_s"][j]),
                    off_start_s=float(nsf["win_start_s"][j]),
                    mask_dc_khz=mask,
                    band_minus_sideband_db=m["band_minus_sideband_db"],
                    linear_sideband_fit_db=m["linear_sideband_fit_db"]))

    write_csv(out / "contrasts_dc.csv", ["on","off","method","mask_dc_khz",
        "band_minus_sideband_db","band_median_db","sideband_median_db",
        "linear_sideband_fit_db","n_band_bins_used","n_sideband_bins_used"],
        ([r[x] for x in ("on","off","method","mask_dc_khz",
        "band_minus_sideband_db","band_median_db","sideband_median_db",
        "linear_sideband_fit_db","n_band_bins_used","n_sideband_bins_used")] for r in comparisons))
    write_csv(out / "windows_dc.csv", ["capture","start_s","end_s","fft_blocks",
        "method","mask_dc_khz","local_feature_db","linear_sideband_fit_db"],
        ([r[x] for x in ("capture","start_s","end_s","fft_blocks",
        "method","mask_dc_khz","local_feature_db","linear_sideband_fit_db")] for r in window_rows))
    write_csv(out / "window_pair_contrasts.csv", ["on","off","window_index",
        "on_start_s","off_start_s","mask_dc_khz","band_minus_sideband_db",
        "linear_sideband_fit_db"],
        ([r[x] for x in ("on","off","window_index","on_start_s","off_start_s",
        "mask_dc_khz","band_minus_sideband_db","linear_sideband_fit_db")] for r in window_pair_rows))

    summary = {
        "version": VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(directory),
        "config": config,
        "methodology": "All complete non-overlapping FFTs; per-FFT complex-mean DC removal before Hann FFT; "
                       "FFT=8192, Hanning window; 0/2/5/10-kHz center masks applied via interpolation "
                       "before smoothing, excluded from band metrics. Ratio baseline 35/341 bins, "
                       "independent linear sideband fit. Windows are correlated and ON/OFF not simultaneous.",
        "dc_checks": dc_checks,
        "full_capture_pairs": comparisons,
        "window_pair_stats": {},
        "limitations": [
            "A positive ON/OFF contrast is not proof of astronomical H I.",
            "The target band intersects the SDR center/DC frequency; masks reduce usable target bandwidth.",
            "Each ON/OFF window index refers to relative capture time, not simultaneous sky measurements.",
            "Within-capture windows are dependent and are not independent astrophysical replications.",
            "No flux-density or brightness-temperature calibration is performed.",
            "No NIST-certified entropy evaluation is performed in this script.",
        ],
    }
    for on, off in PAIRS:
        for mask in config["masks_khz"]:
            vals = np.array([r["band_minus_sideband_db"] for r in window_pair_rows
                             if r["on"] == on and r["off"] == off and r["mask_dc_khz"] == mask],dtype=float)
            summary["window_pair_stats"][f"{on}_{off}_mask{mask:g}kHz"] = {
                "n_windows":len(vals), "mean_db":float(np.mean(vals)),
                "sd_windows_db":float(np.std(vals, ddof=1)) if len(vals)>1 else None,
                "median_db":float(np.median(vals)),
                "positive_fraction":float(np.mean(vals>0)),
                "note":"Indicador descritivo; nao e valor-p ou intervalo de confianca",
            }
    atomic_json(out / "summary_dc.json", summary)
    charts(out, freq, spec, comparisons, config, window_rows)
    with (out / "README.txt").open("w",encoding="utf-8") as f:
        f.write("E7 - Reprocessamento integral com correcao DC por bloco.\n"
                "Enviar para analise: summary_dc.json, contrasts_dc.csv, windows_dc.csv, "
                "window_pair_contrasts.csv, individual_spectra.csv, e7_dc_*.png.\n"
                "Nao e necessario enviar os CU8 (gigabytes) nem cache/*.npz.\n"
                "O resultado nao caracteriza deteccao confirmada de HI ou entropia NIST.\n")
    print("\nCONCLUIDO. Saidas em:", out, flush=True)
    print("Metrica de referencia: full_capture_pairs, method=dc_removed, mask_dc_khz=5 ou 10.")
    print("ATENCAO: mascara de 10 kHz aproxima-se da frequencia candidata; compare com a de 2/5 kHz.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrompido. Reexecute o mesmo comando para continuar capturas ja processadas.",file=sys.stderr)
        sys.exit(130)
    except (OSError, ValueError, MemoryError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)
