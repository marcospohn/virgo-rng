# Como publicar o Virgo-RNG no GitHub (macOS)

## Antes da publicação

Este pacote **ainda não está publicado**. Ele reúne código, resultados numéricos processados e uma amostra curta CU8. Leia `docs/PUBLICATION_CHECKLIST.md` e escolha a licença. Não há documentos LaTeX ou figuras do artigo.

## Método A — Terminal (recomendado)

1. Acesse sua conta GitHub e instale as ferramentas:

```bash
brew install git gh
```

2. Extraia o arquivo ZIP entregue para um diretório, abra Terminal e entre na pasta criada:

```bash
cd ~/Downloads/virgo_rng_github_repository
```

3. Faça a autenticação na **sua conta** GitHub (o navegador solicitará autorização):

```bash
gh auth login --web
```

4. Confira os arquivos e teste o pacote:

```bash
python3 tools/verify_repo.py
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,plot]'
python -m pytest -q tests
```

5. Inicialize o Git e crie um primeiro commit:

```bash
git init -b main
git add -A
git status --short
git commit -m "Initial research release: Virgo-RNG 2.0 and E1-E7 processed data"
```

6. Crie primeiro um repositório **privado** para conferir o conteúdo, e envie o commit:

```bash
gh repo create virgo-rng --private --source=. --remote=origin --push
```

O comando cria o repositório na conta autenticada; não é necessário colocar seu usuário ou senha no script. Visite o link retornado. Quando quiser publicar publicamente, abra a página do repositório no navegador e vá até **Settings > General > Danger Zone > Change repository visibility > Public** (a interface pode mudar). Confirme conscientemente a mudança. Também é possível criar diretamente com `--public` no comando anterior, após concluir a revisão.

> Alternativa sem GitHub CLI: crie um repositório vazio em https://github.com/new (não marque criação de README/License), depois use:
> `git remote add origin https://github.com/SEU_USUARIO/virgo-rng.git` e `git push -u origin main`.

## Atualizar depois

```bash
git status
git add -A
git commit -m "Add revised experimental analysis"
git push
```

Revise `git status` antes de cada envio. Evite adicionar dados sigilosos ou arquivos CU8 extensos diretamente ao Git.

## Publicar os arquivos CU8 originais (opcional)

Os CU8 completos de E1–E7 **não estão no pacote**. O GitHub rejeita objetos Git normais acima de 100 MiB. A opção recomendada para dados maiores é hospedar os CU8 num repositório de dados científico/serviço institucional e adicionar links persistentes e SHA-256 no README. Se você optar por Git LFS, considere os limites de tamanho por arquivo e a cota disponível em sua conta; muitas capturas de 864 MB podem exceder a franquia. Consulte as páginas oficiais do GitHub antes de enviar esses dados.

## Links oficiais

- Documentação da criação de repositórios: https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
- CLI: https://cli.github.com/manual/gh_repo_create
- Limites de repositórios: https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits
- LFS: https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage
