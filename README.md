# Argus

Widget desktop que fica no topo mostrando novidade nos seus chamados do Jira
(Nordware Service Desk) - sem precisar abrir o Jira ou depender de e-mail.

Arquitetura completa e decisões de design em [`ARQUITETURA.md`](ARQUITETURA.md).

## Uso standalone

```bash
uv venv
uv pip install -e .
cp .env.example .env   # preencher JIRA_EMAIL e JIRA_API_TOKEN
python -m argus.app
```

Gere o token em `id.atlassian.com/manage-profile/security/api-tokens` (é um
token de API, não a sua senha).

## Estado atual

Fase 1 (motor + dado, sem personagem) - ver `ARQUITETURA.md`, seção "Fases
sugeridas". A barra mostra os 4 status do fluxo de atendimento
(`assignee = currentUser()`), com toggle novidades/total ao clicar no círculo à
esquerda e lista de tickets ao clicar num número. Personagem animada e
integração com a GAIA ainda não implementadas.
