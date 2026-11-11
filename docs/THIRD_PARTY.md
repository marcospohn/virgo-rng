# Third-party attribution and code provenance

The research code in this repository is the Virgo-RNG experimental project, not the upstream **Virgo** open-source software radio spectrometer. The upstream Virgo spectrometer is a separate project and is not vendored here. External tools, when used locally, may include `rtl_sdr`, `pyrtlsdr`, NumPy, Matplotlib, SciPy, pandas, and the official NIST SP 800-90B EntropyAssessment executables. Those components are not included as third-party source distributions by this package.

- Official NIST reference code: https://github.com/usnistgov/SP800-90B_EntropyAssessment
- GitHub repository: https://github.com/ (user creates the project under their account)

Project history: `legacy/virgo_rng_v1_22/` is a historical research snapshot. Before applying an open-source license to the entire repository, verify code ownership, that contributor permissions are consistent, and whether any copied pieces require additional notices.

Assistance by ChatGPT was substantial in experiment planning support, Python scripting, analysis, visualization and manuscript drafting; the human researcher acquired measurements and retains responsibility for experiments and interpretations. AI is not an author.

<!-- BEGIN VIRGO-UPSTREAM-ATTRIBUTION -->
## Virgo upstream — verified source and license

- Original developer: **Apostolos Spanakis-Misirlis** (with published co-authors and other contributors).
- Source: https://github.com/0xCoto/Virgo
- Upstream source license: **GNU GPL v3** (see the repository's `LICENSE` file).
- Software publication: **Spanakis-Misirlis, Van Eck and Boven (2021), JOSS 6(62), 3067**, https://doi.org/10.21105/joss.03067.
- This Virgo-RNG distribution does not intentionally bundle the upstream source code; code-level provenance must still be audited before relicensing.
- The CC BY 4.0 license of the JOSS article applies to the *article*, not to the Virgo program itself.
- Detailed guidance: [UPSTREAM_VIRGO.md](UPSTREAM_VIRGO.md).
<!-- END VIRGO-UPSTREAM-ATTRIBUTION -->
