# Data availability, provenance, and known gaps

## What the archive really contains

- E1 original and repeat: processed spectra, per-capture JSON metadata, reanalysis of 13 E1/E3 recordings.
- E2: archived tuning-shift spectra; **not full raw CU8 reprocessing**.
- E3: processed load/antenna comparisons plus full-record reanalysis.
- E4/E5: archival first and repeated directional campaigns; **only the repeated E4 campaign was reprocessed from raw CU8** for the E5 broad-band candidate.
- E6: archived ON/OFF spectral contrasts and full-record reanalysis at two receiver center frequencies.
- E7: archived original contrasts, per-window statistics, full-record DC-corrected contrasts, uncertainty and coordinate analyses.
- Preliminary statistics: ABAB, source characterization, predictive tests, NIST-related output, exploratory reports.
- `data/samples/antenna_01_sample.cu8`: small raw sample, separate from the seven-campaign full-record data. Its label is not proof of Galactic HI or entropy certification.

**The complete original CU8 recordings for E1–E7 are NOT included.** Their total size is multiple GB. Only original capture owners can decide to deposit them. The data archive here consists of original archived processed results and scripts derived from them, with labels retaining the processing distinction.

## Integrity

- `data/provenance/FILES.json`: each shared file, source, SHA-256 and whether local path strings were redacted.
- `data/provenance/SOURCE_ARCHIVES.json`: provenance hashes of input ZIPs used for preparation. These ZIPs need not be on GitHub for the hashes to serve as a record.
- `data/provenance/SHA256SUMS.txt`: hashes for research content. Recompute to detect changes.

Local personal home-directory names in text metadata have been replaced with placeholders. Numeric results, frequencies, coordinates and measurement timestamps were otherwise preserved. Review files manually before publishing; automated checks are not a security guarantee.

## Full CU8 publication, if desired

A raw CU8 file contains interleaved unsigned 8-bit I/Q samples. A full E7 180-s capture is about 864 MB, close to GitHub LFS usage limits when several files are uploaded. Use an appropriate research data repository (e.g., institutional storage or Zenodo) to host full measurements and record persistent links and SHA-256 hashes in a separate `RAW_DATA_LINKS.md`. Alternatively use Git LFS after evaluating individual-file limits and account quotas. **Do not commit raw CU8 by ordinary Git.**

Run `python tools/make_raw_manifest.py /path/to/E7_carina --out raw_E7_manifest.json` locally to generate a metadata inventory with SHA-256s, then publish only the manifest if preferred.
