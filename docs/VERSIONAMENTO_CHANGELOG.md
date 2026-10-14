# Versionamento e CHANGELOG do Argus

Mesmo padrão adotado no Project GAIA (repo `Project-GAIA`, ver `docs/VERSIONAMENTO_CHANGELOG.md` de lá) - histórico simples e padronizado, sem cerimônia que não se paga num projeto solo.

## Padrões adotados

- **Semantic Versioning (SemVer)** para a versão global do Argus.
- Categorias em português no `CHANGELOG.md` (Novidades/Alterado/Correções/Segurança), prosa explicando o porquê, não bullets secos em inglês.
- **Sem Conventional Commits.** Fluxo PR-based (`git checkout -b` → `gh pr create` → `gh pr merge --squash --delete-branch`): o squash já produz um commit único e descritivo por PR.

## Regra de versão

```text
MAJOR.MINOR.PATCH
```

- **MAJOR**: alteração grande e incompatível.
- **MINOR**: PR que traz funcionalidade nova compatível com o que já existe.
- **PATCH**: PR que só corrige/ajusta, sem funcionalidade nova relevante.

Manter em `0.x.x` enquanto o projeto ainda estiver evoluindo rapidamente.

## Versão = PR mesclado

A versão nova entra no próprio PR: a entrada do `CHANGELOG.md` já vai sob `## [X.Y.Z] - data`, junto com a versão do `pyproject.toml`, e a tag `vX.Y.Z` é criada depois do merge (regra desde 2026-10-14). `[Unreleased]` fica no topo, sempre vazio: a GAIA compara o primeiro `## [X.Y.Z]` do arquivo para avisar de atualização do Argus, então o que fica em `[Unreleased]` não aparece como versão nova.

## O que entra no CHANGELOG

Funcionalidades novas, mudanças perceptíveis de comportamento, correções importantes (com causa raiz quando vale a pena documentar), recursos removidos, alterações de segurança. Evitar refactor sem mudança perceptível, formatação de código, atualização trivial de dependência.
