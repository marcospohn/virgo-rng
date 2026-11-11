# Virgo (upstream) and Virgo-RNG: attribution and licensing

## Distinct projects

**Virgo** is an open-source radio astronomy spectrometer/radiometer originally created by **Apostolos Spanakis-Misirlis** with contributions from other authors and contributors. Its upstream repository is:

- **Source:** https://github.com/0xCoto/Virgo
- **Upstream software license:** GNU General Public License, version 3 (GPL-3.0); check the `LICENSE` file at the specific upstream revision you use.
- **Scientific software publication:** A. Spanakis-Misirlis, C. L. Van Eck, and E. P. Boven, "Virgo: A Versatile Spectrometer for Radio Astronomy," *Journal of Open Source Software*, vol. 6, no. 62, article 3067 (2021). https://doi.org/10.21105/joss.03067

**Virgo-RNG** is the separately documented experimental SDR/I/Q-entropy research toolkit in this repository. This distribution does **not intentionally vendor the upstream Virgo source tree**. It is **not an official Virgo release**, a fork designated by the upstream authors, or an endorsement by them. The related names do not establish that the source code is shared or that upstream copyright transfers to Virgo-RNG.

## Copyright and the GPL-3.0 license

The upstream GNU GPL v3 permits use, study, modification, and redistribution under its conditions. If any files, code fragments, or derivative works based on the original Virgo software are added to this repository, the maintainers must identify them and comply with the applicable GNU GPL v3 obligations, including retaining required notices, identifying modifications, and providing the corresponding source code and license information to recipients. A combined derivative work may have to be distributed under GPL-compatible terms. Independent programs that only invoke an external executable or use generally known algorithms do not automatically become GPL-covered merely because of that use; a case-specific review is needed for close integration, copying, or derivative code.

The **JOSS paper's Creative Commons Attribution 4.0 license** governs the paper text. It **does not replace the GPL license governing the upstream software**.

This repository has **not yet been assigned a license for the original Virgo-RNG code or processed datasets**. Nothing in this notice grants or chooses such a license. Before selecting MIT, Apache-2.0, GPL-3.0, or a data license, verify the provenance and rights of *all* bundled material, including the historical snapshot in `legacy/` and contributions from other sources.

## Practical use and attribution

- Cite the upstream Virgo project when **Virgo itself** was used; cite the Virgo-RNG research output when **Virgo-RNG** was used, as appropriate.
- Do not claim that an earlier Virgo spectrometer algorithm, source code, or feature was independently developed by Virgo-RNG when it was actually borrowed from upstream.
- Runtime dependencies and external executables (e.g., `rtl_sdr` or NIST reference tools) have separate licenses; consult their notices.
- Do not copy upstream Virgo source files into this repository without performing and recording a license/provenance review.
- The absence of an upstream source directory or obvious `import virgo` statements is **not proof that every historical line was independently written**. A source-level comparison and review of third-party contributions is required before making an unequivocal originality or licensing assertion.

## Suggested BibTeX citation (for upstream Virgo)

```bibtex
@article{SpanakisMisirlis2021Virgo,
  author  = {Spanakis-Misirlis, Apostolos and Van Eck, Cameron L. and Boven, E. P.},
  title   = {Virgo: A Versatile Spectrometer for Radio Astronomy},
  journal = {Journal of Open Source Software},
  year    = {2021},
  volume  = {6},
  number  = {62},
  pages   = {3067},
  doi     = {10.21105/joss.03067}
}
```

*This notice is for research transparency, not a legal opinion or warranty of non-infringement.*
