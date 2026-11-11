#!/usr/bin/env python3
"""Idempotently add documented attribution for upstream Virgo to a Virgo-RNG checkout.

Unpack this update into the existing Git repository root, then run:
    python3 tools/apply_upstream_notice.py --repo .

Preserves existing README content rather than replacing the files wholesale.
"""
from pathlib import Path
import argparse
import hashlib
import json

BEGIN = '<!-- BEGIN VIRGO-UPSTREAM-ATTRIBUTION -->'
END = '<!-- END VIRGO-UPSTREAM-ATTRIBUTION -->'

EN = """{b}
### Relationship to the original Virgo spectrometer

The open-source **Virgo** spectrometer was created by **Apostolos Spanakis-Misirlis** and is distributed under **GNU GPL v3**: https://github.com/0xCoto/Virgo. Its peer-reviewed software paper is Spanakis-Misirlis, Van Eck and Boven (2021), *JOSS*, DOI: https://doi.org/10.21105/joss.03067.

**Virgo-RNG is a separate research toolkit and is not an official Virgo release.** This distribution does not intentionally include the upstream Virgo source tree; this statement is not a line-by-line provenance audit. Incorporating upstream GPL-covered source in the future requires satisfying that license's conditions. Read [upstream attribution and licensing](docs/UPSTREAM_VIRGO.md) before publishing or relicensing. The project code and datasets have **no license assigned in this package**.
{e}
""".format(b=BEGIN,e=END)

PT = """{b}
## Relação com o Virgo original e licença

O espectrômetro **Virgo**, originalmente desenvolvido por **Apostolos Spanakis-Misirlis**, é distribuído sob a licença **GNU GPL v3**: https://github.com/0xCoto/Virgo. Publicação: Spanakis-Misirlis, Van Eck e Boven (2021), *JOSS*, DOI: https://doi.org/10.21105/joss.03067.

**Virgo-RNG é um projeto de pesquisa separado**, e esta distribuição não inclui intencionalmente a árvore de código-fonte do Virgo original. Isso não equivale a uma auditoria integral de similaridade/proveniência. Se houver incorporação de código GPL de terceiros, devem ser respeitadas as obrigações da licença. Veja [a documentação de atribuição e licenciamento](docs/UPSTREAM_VIRGO.md). O código e os dados próprios **ainda não receberam uma licença neste pacote**.
{e}
""".format(b=BEGIN,e=END)

THIRD = """{b}
## Virgo upstream — verified source and license

- Original developer: **Apostolos Spanakis-Misirlis** (with published co-authors and other contributors).
- Source: https://github.com/0xCoto/Virgo
- Upstream source license: **GNU GPL v3** (see the repository's `LICENSE` file).
- Software publication: **Spanakis-Misirlis, Van Eck and Boven (2021), JOSS 6(62), 3067**, https://doi.org/10.21105/joss.03067.
- This Virgo-RNG distribution does not intentionally bundle the upstream source code; code-level provenance must still be audited before relicensing.
- The CC BY 4.0 license of the JOSS article applies to the *article*, not to the Virgo program itself.
- Detailed guidance: [UPSTREAM_VIRGO.md](UPSTREAM_VIRGO.md).
{e}
""".format(b=BEGIN,e=END)

CHECK = """{b}
- [ ] Confirm whether any Virgo upstream GPL-covered source was copied, adapted, or combined into **any** Virgo-RNG or historical module. If so, preserve notices and comply with the applicable GPL terms before publishing.
- [ ] Keep the upstream Virgo citation, copyright attribution, original repository link, and software-vs-paper license distinction in the README and documentation.
- [ ] Do **not** select an MIT/Apache license for the entire repository without clearing third-party and institutional rights; do **not** describe the project as officially endorsed by upstream Virgo.
{e}
""".format(b=BEGIN,e=END)

def put(text, fragment, before=None):
    if BEGIN in text:
        start=text.find(BEGIN)
        stop=text.find(END,start)
        if stop==-1:
            raise ValueError('Existing attribution block is missing its closing marker; review manually')
        stop+=len(END)
        text=text[:start]+fragment.strip()+text[stop:]
    elif before and before in text:
        text=text.replace(before,fragment.strip()+'\n\n'+before,1)
    else:
        text=text.rstrip()+'\n\n'+fragment.strip()+'\n'
    return text

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',type=Path,default=Path('.'),help='Root directory of an existing Virgo-RNG checkout')
    ap.add_argument('--dry-run',action='store_true',help='Check paths and preview planned changes without writing')
    opts=ap.parse_args()
    root=opts.repo.resolve()
    if not (root/'virgo_rng').is_dir() or not (root/'README.md').is_file():
        ap.error('Target does not appear to be Virgo-RNG repository root (README.md and virgo_rng/ needed)')
    up=root/'docs/UPSTREAM_VIRGO.md'
    if not up.is_file():
        ap.error('Missing docs/UPSTREAM_VIRGO.md: extract the update ZIP at the repository root first')
    updates=[
      ('README.md',EN,'**Before publishing publicly:**'),
      ('README.pt-BR.md',PT,None),
      ('docs/THIRD_PARTY.md',THIRD,None),
      ('docs/PUBLICATION_CHECKLIST.md',CHECK,None),
    ]
    for name,block,anchor in updates:
        p=root/name
        if not p.is_file():
            ap.error('Missing expected file: '+name)
        before=p.read_text(encoding='utf-8')
        after=put(before,block,anchor)
        if opts.dry_run:
            print(f'{name}: '+('already current' if before==after else 'would update'))
        elif before!=after:
            p.write_text(after,encoding='utf-8')
            print(f'{name}: updated')
        else:
            print(f'{name}: already current')
    manifest_path=root/'data/provenance/FILES.json'
    if manifest_path.is_file():
        archive=json.loads(manifest_path.read_text(encoding='utf-8'))
        tracked={item['path']:item for item in archive}
        for rel in [name for name,_,_ in updates]+['docs/UPSTREAM_VIRGO.md',
                    'docs/ATUALIZAR_GITHUB_VIRGO.md','tools/apply_upstream_notice.py']:
            fp=root/rel
            item=tracked.get(rel)
            if item is None:
                item={'path':rel,'source':'attribution-update:2026-11',
                      'sha256':'','size_bytes':0,'redacted_paths':False}
                archive.append(item)
            data=fp.read_bytes()
            item['sha256']=hashlib.sha256(data).hexdigest()
            item['size_bytes']=len(data)
        if opts.dry_run:
            print('data/provenance/FILES.json: would refresh modified file hashes')
        else:
            rendered=json.dumps(archive,ensure_ascii=False,indent=2)+'\n'
            if manifest_path.read_text(encoding='utf-8')!=rendered:
                manifest_path.write_text(rendered,encoding='utf-8')
                print('data/provenance/FILES.json: refreshed modified file hashes')
    print('Attribution documentation:',up)
    if opts.dry_run:print('No existing files changed (--dry-run).')

if __name__=='__main__':
    main()
