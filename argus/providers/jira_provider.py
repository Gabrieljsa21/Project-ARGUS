"""Fonte de notificação real - Jira Cloud REST API v3, Basic Auth (e-mail +
API token, não senha). Cobre só o fluxo de atendimento (assignee = você mesmo),
nos 4 status decididos em ARQUITETURA.md - "Em Revisão", "Aguardando
atendimento", "Aguardando cliente" e "Aguardando desenvolvimento".

Heurística de novidade (validada com o usuário, ver ARQUITETURA.md): conta como
novo desde a última vez que o ticket foi ABERTO (não desde a última checagem) -
mudança de status, de prioridade, de responsável, ou comentário de alguém que
não seja o próprio usuário nem uma conta de automação. Comentário automático do
Jira (ex.: aviso de SLA de "Automation for Jira") é ruído, ignorado de propósito.

Vínculo de 2 saltos (categoria "Aguardando desenvolvimento"): quando o ticket
tem um link tipo "Problem/Incident" pro board de dev, a novidade é checada no
ticket VINCULADO, não no ticket de atendimento em si - os devs só comentam lá.
Isso vale pra qualquer ticket com esse vínculo, não só os "Aguardando
desenvolvimento" - a categoria em si não importa pra essa decisão, só o vínculo."""

import requests

from ..modelos import Categoria, Ticket
from ..persistencia import Persistencia
from .base import NotificacaoProvider

CATEGORIAS_STATUS = [
    ("em_revisao", "Em Revisão", "Em Revisão"),
    ("atendimento", "Aguardando Atendimento", "Aguardando atendimento"),
    ("cliente", "Aguardando Cliente", "Aguardando cliente"),
    ("dev", "Aguardando Desenvolvimento", "Aguardando desenvolvimento"),
]

TIPO_VINCULO_DEV = "Problem/Incident"
AUTORES_AUTOMATICOS_IGNORADOS = {"Automation for Jira"}
CAMPOS_ISSUE = "summary,status,priority,updated,assignee,comment,issuelinks"


class JiraProvider(NotificacaoProvider):
    def __init__(self, base_url: str, email: str, api_token: str, persistencia: Persistencia):
        self._base_url = base_url.rstrip("/")
        self._auth = (email, api_token)
        self._persistencia = persistencia
        self._minha_account_id = self._obter_meu_account_id()

    def _obter(self, caminho: str, params: dict | None = None) -> dict:
        resposta = requests.get(f"{self._base_url}{caminho}", auth=self._auth, params=params, timeout=15)
        resposta.raise_for_status()
        return resposta.json()

    def _obter_meu_account_id(self) -> str:
        return self._obter("/rest/api/3/myself")["accountId"]

    def _buscar_issues(self, jql: str) -> list:
        dados = self._obter("/rest/api/3/search", params={
            "jql": jql,
            "fields": CAMPOS_ISSUE,
            "maxResults": 100,
        })
        return dados.get("issues", [])

    def _obter_issue_completo(self, chave: str) -> dict:
        return self._obter(f"/rest/api/3/issue/{chave}", params={"fields": CAMPOS_ISSUE})

    def _issue_vinculado_dev(self, issue: dict) -> dict | None:
        for vinculo in issue["fields"].get("issuelinks", []):
            if vinculo["type"]["name"] != TIPO_VINCULO_DEV:
                continue
            return vinculo.get("inwardIssue") or vinculo.get("outwardIssue")
        return None

    def _resolver_issue_para_novidade(self, issue: dict) -> dict:
        vinculado = self._issue_vinculado_dev(issue)
        if vinculado is None:
            return issue
        return self._obter_issue_completo(vinculado["key"])

    def _eh_autor_automatico(self, nome_exibicao: str) -> bool:
        return nome_exibicao in AUTORES_AUTOMATICOS_IGNORADOS

    def _estado_atual(self, issue: dict) -> dict:
        campos = issue["fields"]
        comentarios = campos.get("comment", {}).get("comments", [])
        ultimo = comentarios[-1] if comentarios else None
        return {
            "status": campos["status"]["name"],
            "prioridade": (campos.get("priority") or {}).get("name"),
            "assignee_id": (campos.get("assignee") or {}).get("accountId"),
            "ultimo_comentario_id": ultimo["id"] if ultimo else None,
            "ultimo_comentario_autor_id": ultimo["author"]["accountId"] if ultimo else None,
            "ultimo_comentario_autor_nome": ultimo["author"].get("displayName", "") if ultimo else None,
        }

    def _eh_novidade(self, visto: dict | None, atual: dict) -> bool:
        if visto is None:
            return True
        if visto.get("status") != atual["status"]:
            return True
        if visto.get("prioridade") != atual["prioridade"]:
            return True
        if visto.get("assignee_id") != atual["assignee_id"]:
            return True
        comentario_novo = atual["ultimo_comentario_id"] and atual["ultimo_comentario_id"] != visto.get("ultimo_comentario_id")
        if comentario_novo:
            autor_id = atual["ultimo_comentario_autor_id"]
            autor_nome = atual["ultimo_comentario_autor_nome"] or ""
            if autor_id != self._minha_account_id and not self._eh_autor_automatico(autor_nome):
                return True
        return False

    def listar_categorias(self) -> list:
        categorias = []
        for chave_cat, nome_cat, nome_status in CATEGORIAS_STATUS:
            jql = f'assignee = currentUser() AND status = "{nome_status}" ORDER BY updated DESC'
            issues = self._buscar_issues(jql)
            tickets = []
            for issue in issues:
                chave_ticket = issue["key"]
                campos = issue["fields"]
                issue_novidade = self._resolver_issue_para_novidade(issue)
                atual = self._estado_atual(issue_novidade)
                visto = self._persistencia.obter_estado_ticket(chave_ticket)
                tickets.append(Ticket(
                    chave=chave_ticket,
                    resumo=campos["summary"],
                    status=campos["status"]["name"],
                    prioridade=(campos.get("priority") or {}).get("name", ""),
                    url=f"{self._base_url}/browse/{chave_ticket}",
                    atualizado_em=campos["updated"],
                    novo=self._eh_novidade(visto, atual),
                ))
            categorias.append(Categoria(chave=chave_cat, nome_exibicao=nome_cat, tickets=tickets))
        return categorias

    def marcar_visto(self, chave_ticket: str) -> None:
        issue = self._obter_issue_completo(chave_ticket)
        issue_novidade = self._resolver_issue_para_novidade(issue)
        estado = self._estado_atual(issue_novidade)
        self._persistencia.salvar_estado_ticket(chave_ticket, estado)
