# Checklist — before making repository public

- [ ] Confirm the researcher's desired repository name and institutional affiliation.
- [ ] Choose an explicit license for code (suggested candidate: MIT) and for data (suggested candidate: CC BY 4.0), **only after confirming ownership**. Apply actual license texts; do not assume this package grants permission to redistribute unowned materials.
- [ ] Check third-party dependencies and provenance of historical modules.
- [ ] Review filenames, CSV/JSON text and original metadata for identifying details, tokens, email addresses, or private location information.
- [ ] Confirm that coordinates and local timestamps are acceptable to publish.
- [ ] Decide whether to retain the small sample CU8 (`data/samples/`).
- [ ] Replace placeholder `CITATION.cff.example` with the real author name and a repository URL after creating the GitHub repository.
- [ ] Choose whether to include original multi-GB CU8 at all. The deposited full records must be accompanied by checksums and data descriptors.
- [ ] Run `python tools/verify_repo.py` and `pytest -q tests`.
- [ ] Make the repository public only after final review.
