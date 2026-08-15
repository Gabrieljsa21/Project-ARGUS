# Argus

Widget desktop de notificação de chamados do Jira (Nordware Service Desk).
Projeto IRMÃO da GAIA (`Project-GAIA`/`assistant`), mas repositório separado —
usável sozinho por colegas da Nordware que não querem a GAIA inteira, e
consumido pela GAIA como dependência (`pip install git+...`).

Arquitetura completa, decisões de design e estado atual: ver `ARQUITETURA.md`
(sempre a fonte da verdade — este arquivo não repete detalhe técnico).

## Documentação — atualizar na hora, nunca acumular

Toda mudança de comportamento enviada ao git (commit/PR) atualiza a
documentação correspondente NO MESMO commit/PR — nunca fica pra depois:

- `ARQUITETURA.md` — qualquer decisão técnica nova ou correção de algo que o
  documento descrevia errado/desatualizado.
- `README.md` — se mudar como usar/configurar o projeto.
- `CHANGELOG.md` — resumo de alto nível sob `[Unreleased]`.

## Git: sempre via Pull Request

```
git checkout -b <branch>
git push -u origin <branch>
gh pr create
gh pr merge --squash --delete-branch
```

Mesclar sem esperar review (fluxo solo). Nunca commit/push direto na branch
principal.
