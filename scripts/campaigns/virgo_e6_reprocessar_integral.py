#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Virgo-RNG E6: reprocessamento integral das seis capturas CU8 (sem novas medidas).

    python virgo_e6_reprocessar_integral.py --dir results/E6_freq_switch

Le os seis CU8 originais de forma sequencial, em lotes pequenos, e usa TODAS as
FFTs completas, com e sem remocao de DC por bloco. Compara as tres observacoes
ON/OFF na MESMA frequencia absoluta (1420.392 MHz), mesmo quando o receptor foi
sintonizado em centros distintos. Cache por captura: repetir o comando retoma.

Requisitos: Python >=3.9, numpy; matplotlib opcional para figuras.
Os arquivos CU8 e os metadados NAO sao modificados.

IMPORTANTE: a regiao de 1420.392 MHz foi selecionada exploratoriamente apos E6,
nao foi um alvo predefinido desse experimento. Excesso ON/OFF positivo nao
identifica inequivocamente emissao galactica H I. Nao inferir significancia
astronomica tratando janelas de tempo da mesma captura como independentes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

VERSION = "1.0.0"
NAMES = ("ON1", "OFF1", "ON2", "OFF2", "ON3", "OFF3")
PAIRS = (("ON1", "OFF1"), ("ON2", "OFF2"), ("ON3", "OFF3"))
CENTERS = {
    "ON1": 1420105752, "OFF1": 1420105752,
    "ON2": 1420705752, "OFF2": 1420705752,
    "ON3": 1420105752, "OFF3": 1420105752,
}
RATE_DEFAULT = 2_400_000
TARGET_DEFAULT = 1_420_392_000
EPS = 1e-30


def atomic_json(path: Path, content: dict) -> None:
    temp = path.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False, allow_nan=False)
    os.replace(temp, path)


def csv_write(path: Path, headers: list[str], rows) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    os.replace(temp, path)


def read_metadata(folder: Path, rate: int, allow_partial: bool = False) -> dict:
    path = folder / "metadata.json"
    if not path.is_file():
        raise ValueError(f"Metadados ausentes: {path}. Confira --dir.")
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("metadata.json do E6 deve conter uma lista de seis registros")
    by_name = {}
    for rec in records:
        if not isinstance(rec, dict) or not isinstance(rec.get("name"), str):
            raise ValueError("Registro invalido em metadata.json")
        if rec["name"] in by_name:
            raise ValueError(f"Nome duplicado no metadata.json: {rec['name']}")
        by_name[rec["name"]] = rec
    for name in NAMES:
        if name not in by_name:
            raise ValueError(f"Nao encontrei {name} no metadata.json")
        rec = by_name[name]
        c = int(rec.get("center_hz", -1))
        if c != CENTERS[name]:
            raise ValueError(f"{name}: centro esperado {CENTERS[name]}, metadados mostram {c}")
        sr = int(rec.get("rate_hz", rec.get("sample_rate_hz", -1)))
        if sr != rate:
            raise ValueError(f"{name}: taxa no metadata.json {sr} nao corresponde a --rate {rate}")
        if rec.get("pointing") and rec["pointing"].upper() != name[:2 if name.startswith("ON") else 3]:
            # The values are 'ON'/'OFF'; protects against accidental swapped files.
            raise ValueError(f"{name}: apontamento inesperado {rec['pointing']}")
        fp = folder / (name + ".cu8")
        if not fp.is_file():
            raise ValueError(f"CU8 nao encontrado: {fp}")
        sz = fp.stat().st_size
        if sz % 2:
            raise ValueError(f"{name}: CU8 tem quantidade impar de bytes")
        if sz < 4 * 8192:
            raise ValueError(f"{name}: CU8 anormalmente pequeno")
        exp = int(rec.get("bytes", -1))
        if not allow_partial and exp != sz:
            raise ValueError(f"{name}: CU8 tem {sz} bytes; metadata.json informa {exp}; nao prosseguirei")
    return by_name


def moving_average(signal: np.ndarray, width: int) -> np.ndarray:
    if width <= 0 or width % 2 != 1:
        raise ValueError("Comprimento do filtro deve ser impar e positivo")
    if width == 1:
        return np.array(signal, copy=True)
    half = width // 2
    return np.convolve(np.pad(signal, (half, half), mode="reflect"),
                       np.full(width, 1 / width), mode="valid")


def odd_bins(hz: float, resolution: float) -> int:
    v = max(1, int(round(hz / resolution)))
    return v if v % 2 == 1 else v + 1


def remove_dc_ratio(freq: np.ndarray, ratio_db: np.ndarray, center_hz: int,
                    mask_khz: float) -> np.ndarray:
    """Interpola apenas no calculo do residual; mascara nao altera os CU8 nem o PSD."""
    if mask_khz <= 0:
        return ratio_db.copy()
    masked = np.abs(freq - center_hz) <= mask_khz * 1000.0
    if masked.sum() == 0:
        return ratio_db.copy()
    remaining = ~masked
    if remaining.sum() < 2:
        raise ValueError("Mascara remove todos os canais")
    return np.interp(freq, freq[remaining], ratio_db[remaining])


def residuals(freq: np.ndarray, on_power: np.ndarray, off_power: np.ndarray,
              center: int, mask_khz: float, smooth_bins: int,
              baseline_bins: int) -> tuple[np.ndarray, np.ndarray]:
    raw = 10.0 * np.log10(np.maximum(on_power, EPS) / np.maximum(off_power, EPS))
    prepared = remove_dc_ratio(freq, raw, center, mask_khz)
    smoothed = moving_average(prepared, smooth_bins)
    return raw, smoothed - moving_average(smoothed, baseline_bins)


def target_measurement(freq: np.ndarray, raw_ratio: np.ndarray,
                       res: np.ndarray, center: int, target: int,
                       half_khz: float, mask_khz: float) -> dict:
    offset = (freq - target) / 1000.0
    band = np.abs(offset) <= half_khz
    sides = (np.abs(offset) >= 2 * half_khz) & (np.abs(offset) <= 4 * half_khz)
    if mask_khz:
        valid = np.abs(freq - center) > mask_khz * 1000.0
        band &= valid
        sides &= valid
    if np.count_nonzero(band) < 5 or np.count_nonzero(sides) < 10:
        raise ValueError("Faixas de candidato/controle sem canais suficientes")
    band_median = float(np.median(res[band]))
    side_median = float(np.median(res[sides]))
    feature = band_median - side_median
    # Independent of the 100-kHz high-pass: straight line fitted ONLY to sidebands.
    coef = np.polyfit(offset[sides], raw_ratio[sides], deg=1)
    alternative = float(np.median(raw_ratio[band] - np.polyval(coef, offset[band])))
    # Exploratory maximum, not a fitted/LSR-corrected line center or an independent test.
    band_freq = freq[band]
    band_residual = res[band]
    peak_idx = int(np.argmax(band_residual))
    return {
        "band_minus_sideband_db": feature,
        "band_median_db": band_median,
        "sideband_median_db": side_median,
        "linear_sideband_fit_db": alternative,
        "exploratory_peak_hz": float(band_freq[peak_idx]),
        "exploratory_peak_db": float(band_residual[peak_idx]),
        "n_target_bins": int(np.count_nonzero(band)),
        "n_sideband_bins": int(np.count_nonzero(sides)),
    }


def process_full_cu8(path: Path, rate: int, fft: int, window_seconds: float,
                     batch_blocks: int) -> dict:
    """Streaming per-window exact processing of complete, non-overlapping FFTs.

    Ft_corrected = FFT(iq * hann) - mean(iq) * FFT(hann) is identical to
    FFT((iq - mean(iq)) * hann), and avoids a second FFT per block.
    """
    raw = np.memmap(path, dtype=np.uint8, mode="r")
    samples = raw.size // 2
    total_blocks = samples // fft
    if total_blocks < 2:
        raise ValueError(f"{path}: menos de duas FFTs")
    # Split the sequence by whole FFTs. Windows never overlap and no block straddles them.
    blocks_per_window = max(1, int(round(window_seconds * rate / fft)))
    n_windows = (total_blocks + blocks_per_window - 1) // blocks_per_window
    win = np.hanning(fft).astype(np.float32)
    fft_win = np.fft.fft(win)
    sum_uncorrected = np.zeros(fft, np.float64)
    sum_corrected = np.zeros(fft, np.float64)
    window_before = []
    window_after = []
    window_info = []
    dc_sum = 0j
    dc_second = 0.0
    for iw in range(n_windows):
        a_block = iw * blocks_per_window
        z_block = min(total_blocks, a_block + blocks_per_window)
        accum_before = np.zeros(fft, np.float64)
        accum_after = np.zeros(fft, np.float64)
        for j in range(a_block, z_block, batch_blocks):
            n = min(batch_blocks, z_block - j)
            start_byte = j * fft * 2
            stop_byte = (j + n) * fft * 2
            chunk = np.asarray(raw[start_byte:stop_byte], dtype=np.float32).reshape(n, fft, 2)
            iq = (chunk[:, :, 0] - 127.5) + 1j * (chunk[:, :, 1] - 127.5)
            mean = np.mean(iq, axis=1)
            dc_sum += np.sum(mean)
            dc_second += float(np.sum(np.abs(mean) ** 2))
            ft = np.fft.fft(iq * win, axis=1)
            accum_before += np.sum(np.abs(ft)**2, axis=0)
            ft -= mean[:, None] * fft_win[None, :]
            accum_after += np.sum(np.abs(ft)**2, axis=0)
        count = z_block - a_block
        sum_uncorrected += accum_before
        sum_corrected += accum_after
        window_before.append(np.fft.fftshift(accum_before / count))
        window_after.append(np.fft.fftshift(accum_after / count))
        window_info.append((a_block * fft / rate, z_block * fft / rate, count))
        print(f"    {path.stem}: janela {iw + 1}/{n_windows}, {count} FFTs", flush=True)
    del raw
    return {
        "psd_raw": np.fft.fftshift(sum_uncorrected / total_blocks),
        "psd_dc": np.fft.fftshift(sum_corrected / total_blocks),
        "w_raw": np.stack(window_before),
        "w_dc": np.stack(window_after),
        "window_info": np.asarray(window_info, dtype=np.float64),
        "blocks": np.asarray(total_blocks, dtype=np.int64),
        "samples": np.asarray(samples, dtype=np.int64),
        "discarded_samples": np.asarray(samples - total_blocks * fft, dtype=np.int64),
        "dc_mean_i": np.asarray(dc_sum.real / total_blocks, dtype=np.float64),
        "dc_mean_q": np.asarray(dc_sum.imag / total_blocks, dtype=np.float64),
        "dc_rms": np.asarray(np.sqrt(dc_second / total_blocks), dtype=np.float64),
    }


def cached_capture(path: Path, out: Path, name: str, rec: dict,
                   args) -> dict:
    cache_dir = out / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"{name}_full_spectra.npz"
    st = path.stat()
    stamp = {
        "version": VERSION, "name": name, "bytes": st.st_size,
        "mtime_ns": st.st_mtime_ns, "center_hz": int(rec["center_hz"]),
        "rate": args.rate, "fft": args.fft,
        "window_seconds": args.window_seconds,
    }
    if not args.force and cache.is_file():
        try:
            with np.load(cache, allow_pickle=False) as z:
                found = json.loads(str(z["stamp"].item()))
                if found == stamp and z["psd_raw"].shape == (args.fft,) and z["psd_dc"].shape == (args.fft,):
                    print(f"  {name}: usando cache de captura completa.", flush=True)
                    return {key: z[key].copy() for key in z.files if key != "stamp"}
        except (ValueError, OSError, KeyError, json.JSONDecodeError):
            print(f"  {name}: cache inconsistente, recalculando.", flush=True)
    print(f"  {name}: processando todo {path.name} ({st.st_size/1e6:.0f} MB)", flush=True)
    result = process_full_cu8(path, args.rate, args.fft, args.window_seconds, args.batch_blocks)
    temp = cache_dir / f".{name}_temp.npz"
    with temp.open("wb") as f:
        np.savez_compressed(f, stamp=json.dumps(stamp), **result)
    os.replace(temp, cache)
    print(f"  {name}: cache salvo.", flush=True)
    return result


def plot_results(output: Path, freq_axes: dict, spectra: dict, pair_data: list,
                target: float, center_by_name: dict, window_rows: list) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FormatStrFormatter
    except ImportError:
        print("matplotlib ausente: graficos ignorados (CSV/JSON gerados).", flush=True)
        return
    fig, axs = plt.subplots(2, 1, figsize=(10.3, 7.2), constrained_layout=True)
    colors = {"ON1/OFF1":"tab:blue", "ON2/OFF2":"tab:orange", "ON3/OFF3":"tab:green"}
    for d in pair_data:
        if d["method"] != "dc_removed" or d["baseline_khz"] != 100.0 or d["center_mask_khz"] != 5.0:
            continue
        pair = d["pair"]
        f = freq_axes[d["on"]]
        local = (f >= target - 180_000) & (f <= target + 180_000)
        axs[0].plot(f[local]/1e6, d["residual"][local], lw=1.0, label=f"{pair} ({center_by_name[d['on']]/1e6:.6f} MHz)", color=colors[pair])
        axs[1].plot((f[local] - center_by_name[d["on"]])/1000, d["residual"][local], lw=1.0, label=pair, color=colors[pair])
    axs[0].axvspan((target-20_000)/1e6, (target+20_000)/1e6, color="gray", alpha=0.14)
    axs[0].axvline(target/1e6, ls=":", c="black", lw=0.85)
    axs[0].set(xlabel="Frequencia RF absoluta (MHz)", ylabel="Excesso residual ON/OFF (dB)",
               title="E6: mesma candidata em frequencia RF absoluta, duas sintonias")
    axs[0].xaxis.set_major_formatter(FormatStrFormatter("%.3f"))
    axs[0].tick_params(axis="x", labelsize=8)
    axs[0].legend(fontsize=8)
    axs[0].grid(alpha=.2)
    axs[1].set(xlabel="Frequencia relativa ao centro do SDR (kHz)",
               ylabel="Excesso residual ON/OFF (dB)",
               title="As mesmas curvas em coordenadas de banda-base")
    axs[1].legend(fontsize=8)
    axs[1].grid(alpha=.2)
    fig.savefig(output/"e6_absolute_vs_baseband.png", dpi=170)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10,4.2), constrained_layout=True)
    labels = list(NAMES)
    for i,name in enumerate(labels):
        vals = [row for row in window_rows if row["name"] == name and row["method"] == "dc_removed" and row["baseline_khz"] == 100 and row["mask_khz"] == 5]
        for j,v in enumerate(vals):
            xx = i + 0.08 + (j+0.5)*.84/max(1,len(vals))
            ax.scatter(xx, v["feature_db"], s=16, c=("tab:blue" if name.startswith("ON") else "tab:orange"))
    ax.axhline(0, lw=.9, c="gray")
    ax.set_xticks(np.arange(len(labels))+.5, labels)
    ax.set(xlabel="Capturas (janelas em ordem dentro de cada captura)",
           ylabel="Excesso local apos DC (dB)",
           title="E6: evolucao temporal (janelas nao sao sessoes independentes)")
    ax.grid(alpha=.22)
    fig.savefig(output/"e6_temporal.png", dpi=170)
    plt.close(fig)


def make_zip(out: Path) -> Path:
    dest = out.parent / "E6_reprocessamento_resultados.zip"
    include = {".csv", ".json", ".txt", ".md", ".png"}
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.iterdir()):
            if f.is_file() and f.suffix.lower() in include:
                z.write(f, arcname=f.name)
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=Path("results/E6_freq_switch"),
                    help="Diretorio original dos CU8 do E6")
    ap.add_argument("--output", type=Path, default=None,
                    help="Destino de resultados (padrao: DIR/analysis_integral_dc)")
    ap.add_argument("--fft", type=int, default=8192)
    ap.add_argument("--rate", type=int, default=RATE_DEFAULT)
    ap.add_argument("--target-hz", type=int, default=TARGET_DEFAULT)
    ap.add_argument("--half-width-khz", type=float, default=20.)
    ap.add_argument("--window-seconds", type=float, default=10.)
    ap.add_argument("--batch-blocks", type=int, default=96)
    ap.add_argument("--smooth-khz", type=float, default=10.25)
    ap.add_argument("--baseline-khz", nargs="+", type=float, default=[50.,100.,150.])
    ap.add_argument("--center-masks-khz", nargs="+", type=float, default=[0.,5.,10.])
    ap.add_argument("--force", action="store_true", help="Ignora cache e refaz leitura completa")
    ap.add_argument("--check-only", action="store_true", help="Valida arquivos e mostra resumo, sem processar")
    args = ap.parse_args(argv)
    if args.fft < 512 or args.fft & (args.fft-1):
        ap.error("--fft deve ser potencia de 2 >= 512")
    if args.rate <= 0 or args.window_seconds <= 0 or args.batch_blocks <= 0:
        ap.error("--rate, --window-seconds e --batch-blocks devem ser positivos")
    if args.smooth_khz <= 0 or args.half_width_khz <= 0 or any(b<=0 for b in args.baseline_khz):
        ap.error("larguras de bandas devem ser positivas")
    if any(b < 0 for b in args.center_masks_khz):
        ap.error("mascaras devem ser >= 0")
    try:
        records = read_metadata(args.dir, args.rate)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as ex:
        ap.error(str(ex))
    print("E6: seis capturas verificadas (nenhuma aquisicao sera executada).")
    for name in NAMES:
        rec = records[name]
        print(f"  {name:<4} {rec['center_hz']/1e6:.6f} MHz | "
              f"{(args.dir/(name+'.cu8')).stat().st_size/1e6:.1f} MB | "
              f"az/el {rec.get('azimuth_deg','?')}/{rec.get('elevation_deg','?')}")
    if args.check_only:
        return 0

    out = args.output or args.dir/"analysis_integral_dc"
    out.mkdir(parents=True, exist_ok=True)
    resolution = args.rate/args.fft
    smooth_bins = odd_bins(args.smooth_khz*1000, resolution)
    baselines = sorted({float(b) for b in args.baseline_khz})
    masks = sorted({float(m) for m in args.center_masks_khz})
    base_bins = {b:odd_bins(b*1000, resolution) for b in baselines}
    config = {"version":VERSION,"fft":args.fft,"rate_hz":args.rate,
              "resolution_hz":resolution,"smooth_bins":smooth_bins,
              "smoothing_khz_actual":smooth_bins*resolution/1000,
              "baseline_bins":{str(k):v for k,v in base_bins.items()},
              "target_hz":args.target_hz,"half_width_khz":args.half_width_khz,
              "window_seconds":args.window_seconds,
              "masks_khz":masks,"baselines_khz":baselines}
    spectra = {}; freq_axes = {}
    for name in NAMES:
        spectra[name] = cached_capture(args.dir/(name+".cu8"),out,name,records[name],args)
        freq_axes[name] = int(records[name]["center_hz"]) + np.fft.fftshift(np.fft.fftfreq(args.fft, 1/args.rate))

    # Audit of DC-bin reduction; note that the candidate is ~300 kHz from the center.
    audit = {}
    for name in NAMES:
        center = int(records[name]["center_hz"])
        freq = freq_axes[name]
        k = int(np.argmin(np.abs(freq-center)))
        s = spectra[name]
        audit[name] = {
            "center_hz": center,
            "target_offset_from_center_khz": (args.target_hz-center)/1000,
            "center_bin_reduction_db":float(10*np.log10(max(s["psd_dc"][k],EPS)/max(s["psd_raw"][k],EPS))),
            "fft_blocks_used":int(s["blocks"]),
            "complex_samples":int(s["samples"]),
            "fraction_omitted_last_partial_fft":float(int(s["discarded_samples"])/int(s["samples"])),
            "mean_block_dc_i":float(s["dc_mean_i"]),
            "mean_block_dc_q":float(s["dc_mean_q"]),
            "rms_block_dc":float(s["dc_rms"]),
        }

    # Export full PSD (uncalibrated units) and every pair's frequency axis.
    csv_write(out/"individual_spectra.csv",
              ["capture","center_hz","frequency_hz","offset_baseband_hz","power_before_dc","power_after_dc"],
              ([name,int(records[name]["center_hz"]),f,f-int(records[name]["center_hz"]),p,q]
               for name in NAMES for f,p,q in zip(freq_axes[name],spectra[name]["psd_raw"],spectra[name]["psd_dc"])))

    full_pair_rows = []
    pair_spectrum_rows = []
    pair_figs = []
    for on, off in PAIRS:
        c = int(records[on]["center_hz"])
        assert c == int(records[off]["center_hz"]), "ON/OFF com centros distintos"
        freq = freq_axes[on]
        if not np.array_equal(freq, freq_axes[off]):
            raise ValueError(f"Incompatibilidade de eixos {on}/{off}")
        for col, method in (("psd_raw", "before_dc"),("psd_dc", "dc_removed")):
            for mask in masks:
                for baseline in baselines:
                    raw_ratio, res = residuals(freq,spectra[on][col],spectra[off][col],c,
                                               mask,smooth_bins,base_bins[baseline])
                    m = target_measurement(freq,raw_ratio,res,c,args.target_hz,args.half_width_khz,mask)
                    row = {"pair":f"{on}/{off}", "on":on, "off":off,"center_hz":c,
                           "target_offset_khz":(args.target_hz-c)/1000,
                           "method":method,"center_mask_khz":mask,
                           "baseline_khz":baseline,**m}
                    full_pair_rows.append(row)
                    if method=="dc_removed" and mask==5. and baseline==100.:
                        pair_figs.append({**row,"residual":res.copy()})
                    if baseline==100. and mask==5.:
                        for f, rr, r in zip(freq, raw_ratio, res):
                            pair_spectrum_rows.append((f"{on}/{off}",method,c,f,f-c,rr,r))

    fields = ["pair","on","off","center_hz","target_offset_khz","method","center_mask_khz",
              "baseline_khz","band_minus_sideband_db","band_median_db","sideband_median_db",
              "linear_sideband_fit_db","exploratory_peak_hz","exploratory_peak_db",
              "n_target_bins","n_sideband_bins"]
    csv_write(out/"contrasts_e6_integral.csv",fields,
              ([r[c] for c in fields] for r in full_pair_rows))
    csv_write(out/"pair_spectra_dc.csv",
              ["pair","method","center_hz","frequency_hz","baseband_offset_hz","raw_on_off_db","residual_db"],
              pair_spectrum_rows)

    # Window-level local band-minus-sideband relative to each recording's baseline.
    # Quantifies stability; it is not a matched simultaneous ON/OFF estimator.
    window_rows = []
    for name in NAMES:
        c = int(records[name]["center_hz"])
        f = freq_axes[name]
        spec = spectra[name]
        for k, (a,b,blocks) in enumerate(spec["window_info"]):
            for col,method in (("w_raw","before_dc"),("w_dc","dc_removed")):
                power = spec[col][k]
                db = 10*np.log10(np.maximum(power,EPS))
                for mask in (5.,):
                    cleaned = remove_dc_ratio(f,db,c,mask)
                    sm = moving_average(cleaned,smooth_bins)
                    res = sm-moving_average(sm,base_bins.get(100.,next(iter(base_bins.values()))))
                    m=target_measurement(f,db,res,c,args.target_hz,args.half_width_khz,mask)
                    window_rows.append({"name":name,"method":method,"window_index":k,
                        "start_s":float(a),"end_s":float(b),"fft_blocks":int(blocks),
                        "mask_khz":mask,"baseline_khz":100.,"feature_db":m["band_minus_sideband_db"],
                        "linear_sideband_fit_db":m["linear_sideband_fit_db"]})
    wfields=["name","method","window_index","start_s","end_s","fft_blocks",
             "mask_khz","baseline_khz","feature_db","linear_sideband_fit_db"]
    csv_write(out/"windows_e6_integral.csv",wfields,
              ([r[c] for c in wfields] for r in window_rows))
    # When window counts happen to match, ON/OFF ratios of their PSDs are a descriptive
    # temporal diagnostic; windows with matching index are NOT simultaneous measurements.
    pair_window_rows=[]
    for on,off in PAIRS:
        f = freq_axes[on]
        c=int(records[on]["center_hz"])
        son,soff=spectra[on],spectra[off]
        num=min(len(son["window_info"]),len(soff["window_info"]))
        for k in range(num):
            raw_ratio,res = residuals(f,son["w_dc"][k],soff["w_dc"][k],c,
                                      5.,smooth_bins,base_bins.get(100.,next(iter(base_bins.values()))))
            m = target_measurement(f,raw_ratio,res,c,args.target_hz,args.half_width_khz,5.)
            pair_window_rows.append({"pair":f"{on}/{off}","index":k,
                                     "on_start_s":float(son["window_info"][k,0]),
                                     "off_start_s":float(soff["window_info"][k,0]),
                                     "feature_db":m["band_minus_sideband_db"],
                                     "linear_fit_db":m["linear_sideband_fit_db"]})
    pwfields=["pair","index","on_start_s","off_start_s","feature_db","linear_fit_db"]
    csv_write(out/"pair_windows_e6.csv",pwfields,([r[c] for c in pwfields] for r in pair_window_rows))

    group_stats={}
    for on,off in PAIRS:
        key=f"{on}/{off}"
        a=np.asarray([r["feature_db"] for r in pair_window_rows if r["pair"]==key], dtype=float)
        group_stats[key]={"n_windows":len(a),
                          "mean_db":float(np.mean(a)),
                          "sd_window_db":float(np.std(a,ddof=1)) if len(a)>1 else None,
                          "positive_fraction":float(np.mean(a>0)),
                          "minimum_db":float(np.min(a)), "maximum_db":float(np.max(a))}
    summary={
        "timestamp_utc":datetime.now(timezone.utc).isoformat(),"script":VERSION,
        "input_dir":str(args.dir),"output_dir":str(out),"parameters":config,
        "captures":{n:{**records[n],**audit[n]} for n in NAMES},
        "full_capture_contrasts":full_pair_rows,
        "temporal_descriptives":group_stats,
        "scientific_notes":[
            "E6 candidate frequency 1420.392 MHz was selected after inspecting E6; this is exploratory for E6.",
            "E6 ON1/ON3 and ON2 use different receiver centers: see target_offset_khz.",
            "ON/OFF comparisons share a tuning within a pair, but receiver bandpass may differ across tunings.",
            "DC correction removes complex mean separately in each full FFT block, not just central bin clipping.",
            "Absence of center DC artifact does not rule out external RFI fixed at an absolute RF frequency.",
            "ON/OFF are separated in time; pair windows refer to elapsed time within different recordings.",
            "Baseline and mask sensitivity remain diagnostics, not independent repetitions or p-values.",
            "No absolute calibration of antenna temperature, direction-dependent system gain, or LSR correction.",
            "A positive residual does not by itself confirm Galactic hydrogen or a usable random-number source.",
        ],
    }
    atomic_json(out/"summary_e6_integral.json",summary)
    plot_results(out,freq_axes,spectra,pair_figs,args.target_hz,
                 {n:int(records[n]["center_hz"]) for n in NAMES},window_rows)
    readme=(
        "E6 | Reprocessamento integral com correcao DC e comparacao RF absoluta\n\n"
        f"Alvo exploratorio: {args.target_hz} Hz, janela ±{args.half_width_khz:g} kHz.\n"
        "Seis arquivos CU8 lidos integralmente. FFT Hann, correcao DC por bloco.\n"
        "Os arquivos CU8 e metadata.json nao foram modificados.\n\n"
        "Analise principal: contrasts_e6_integral.csv, method=dc_removed, "
        "center_mask_khz=5, baseline_khz=100.\n"
        "Compare 50/100/150 kHz e before_dc para avaliar sensibilidade.\n"
        "Veja summary_e6_integral.json e os graficos PNG.\n"
        "As janelas temporais nao sao experimentos independentes, nem ON/OFF simultaneos.\n"
        "Nao se declara deteccao confirmada de H I nem significancia estatistica.\n"
    )
    (out/"README.txt").write_text(readme, encoding="utf-8")
    packet = make_zip(out)
    print("\nCONCLUIDO. Pares, apos correcao DC e baseline 100 kHz, mascara 5 kHz:")
    for rec in full_pair_rows:
        if rec["method"]=="dc_removed" and rec["center_mask_khz"]==5. and rec["baseline_khz"]==100.:
            print(f"  {rec['pair']}: {rec['band_minus_sideband_db']:+.5f} dB; "
                  f"centro SDR {rec['center_hz']/1e6:.6f} MHz")
    print(f"Resultados: {out}\nZIP sem CU8 para enviar: {packet}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrompido. Execute novamente para retomar a partir do cache de cada captura.",file=sys.stderr)
        sys.exit(130)
    except (OSError, ValueError, MemoryError, AssertionError) as err:
        print(f"ERRO: {err}",file=sys.stderr)
        sys.exit(1)
