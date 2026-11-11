# Atualização da atribuição ao Virgo original — GitHub

Esta atualização não substitui nem republica os dados experimentais. Ela acrescenta o documento `docs/UPSTREAM_VIRGO.md` e integra avisos em README, documentação de terceiros e checklist.

## Aplicar a atualização a um repositório Git já existente no Mac

1. Baixe `Virgo_RNG_Upstream_Attribution_Update.zip` para `~/Downloads/`.
2. Entre **na pasta do repositório local que já está ligada ao GitHub**; se não estiver no Mac, clone o repositório primeiro:

```bash
gh repo clone SEU_USUARIO/virgo-rng
cd virgo-rng
```

3. Verifique se não há alterações locais pendentes:

```bash
git status --short
git remote -v
```

4. Extraia **somente este pacote de atualização** na raiz do repositório:

```bash
unzip -o ~/Downloads/Virgo_RNG_Upstream_Attribution_Update.zip
```

5. Atualize os avisos dos arquivos existentes sem sobrescrever outras partes:

```bash
python3 tools/apply_upstream_notice.py --repo .
python3 tools/verify_repo.py
git diff -- README.md README.pt-BR.md docs/THIRD_PARTY.md docs/PUBLICATION_CHECKLIST.md
```

6. Faça um commit restrito aos arquivos desta atualização e envie para o branch atual:

```bash
git add README.md README.pt-BR.md docs/THIRD_PARTY.md docs/PUBLICATION_CHECKLIST.md docs/UPSTREAM_VIRGO.md docs/ATUALIZAR_GITHUB_VIRGO.md tools/apply_upstream_notice.py data/provenance/FILES.json
git diff --cached --stat
git commit -m "Document upstream Virgo attribution and GPL-3.0 terms"
git push origin "$(git branch --show-current)"
```

Use `git status` para confirmar que não incluiu mudanças ou dados privados inadvertidamente. Se o repositório ainda não existe no GitHub, siga `docs/COMO_PUBLICAR_GITHUB.md` para criá-lo primeiro.

**Observação:** não foi atribuída uma licença ao código próprio do Virgo-RNG. Não use estes avisos como confirmação de ausência de código derivado da GPL; confira a proveniência antes da divulgação pública.
