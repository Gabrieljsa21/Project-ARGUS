"""Validação offline das MRs vinculadas (2026-10-01, ver docs/ARQUITETURA.md
"MRs vinculadas") - sem rede: `JiraProvider` montado sem `__init__` e com
`_obter` respondendo o painel "Desenvolvimento" do Jira (`/rest/dev-status`).
Confirma leitura de GitLab (com aprovadores) e Gitea (sem revisores), os
eventos de aprovação nova / mesclada / comentário novo, a linha de base para
estado antigo sem MRs e que falha na API não derruba nem inventa evento.
Rodar a partir da raiz do projeto:

    .venv/Scripts/python.exe testes/testar_mrs.py
"""

import os
import sys
import tempfile

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from argus.persistencia import PersistenciaArquivo
from argus.providers.jira_provider import JiraProvider

GITLAB = "oAuth-gitlab"
GITEA = "oAuth-gitea"


def _issue():
    return {"key": "PLATZ-1", "id": "100", "fields": {
        "summary": "Resumo", "status": {"name": "Code Review"}, "priority": {"name": "Medium"},
        "updated": "2026-10-01", "assignee": None, "reporter": None, "description": None,
        "attachment": [], "comment": {"comments": []}, "issuelinks": [],
    }}


class _JiraFalso:
    def __init__(self):
        self.gitlab = {"id": "bringitbr/platz/platz.core!10", "name": "Corrige X", "status": "OPEN",
                       "url": "https://gitlab.com/mr/10", "commentCount": 0, "repositoryName": "platz.core",
                       "reviewers": [{"name": "Rafael", "approved": False}, {"name": "Lucas", "approved": False}]}
        self.gitea = {"id": "#56", "name": "Ajusta Y", "status": "OPEN", "url": "https://git.nordware.io/pulls/56",
                      "commentCount": 0, "repositoryName": "sbone", "reviewers": []}
        self.falhar = False

    def obter(self, caminho, params=None, tentativas=3):
        if caminho == "/rest/api/3/search/jql":
            return {"issues": [_issue()] if "status in (13157)" in params["jql"] else []}
        if caminho.startswith("/rest/dev-status/"):
            if self.falhar:
                raise requests.ConnectionError("sem rede")
            if caminho.endswith("/summary"):
                return {"summary": {"pullrequest": {"byInstanceType": {
                    GITLAB: {"count": 1}, GITEA: {"count": 1}}}}}
            mr = self.gitlab if params["applicationType"] == GITLAB else self.gitea
            return {"detail": [{"pullRequests": [dict(mr, reviewers=[dict(r) for r in mr["reviewers"]])]}]}
        if caminho.startswith("/rest/servicedeskapi/"):
            raise requests.HTTPError("sem SLA")
        return _issue()


def main():
    caminho = os.path.join(tempfile.gettempdir(), "argus_teste_mrs.json")
    if os.path.exists(caminho):
        os.remove(caminho)
    persistencia = PersistenciaArquivo(caminho)
    persistencia.salvar_configuracoes({"perfil": "n2"})
    jira = _JiraFalso()
    provider = JiraProvider.__new__(JiraProvider)
    provider._base_url = "https://example.atlassian.net"
    provider._persistencia = persistencia
    provider._persistencia_configuracoes = persistencia
    provider._descrever_imagem = None
    provider._minha_account_id = "eu"
    provider._obter = jira.obter
    falhas = []

    def checar(descricao, ok):
        print(("OK: " if ok else "FALHA: ") + descricao)
        if not ok:
            falhas.append(descricao)

    def ticket():
        return next(t for c in provider.listar_categorias() for t in c.tickets if t.chave == "PLATZ-1")

    t = ticket()
    por_rotulo = {m["rotulo"]: m for m in t.mrs}
    checar("lê MR do GitLab e do Gitea", set(por_rotulo) == {"platz.core!10", "sbone#56"})
    checar("status legível", por_rotulo["platz.core!10"]["status_legivel"] == "Aberta")

    provider.marcar_visto("PLATZ-1")
    checar("sem mudança, sem novidade", not ticket().novo)

    jira.gitlab["reviewers"][0]["approved"] = True
    t = ticket()
    checar("aprovação nova vira novidade", t.novo and t.tipo_evento == "mr_aprovada")
    checar("detalhe diz quem aprovou", t.detalhe_evento == "aprovada por Rafael (1 aprovação)")
    provider.marcar_visto("PLATZ-1")

    jira.gitlab["reviewers"][1]["approved"] = True
    jira.gitlab["commentCount"] = 2
    t = ticket()
    checar("aprovação tem prioridade sobre comentário", t.tipo_evento == "mr_aprovada"
           and t.detalhe_evento == "aprovada por Lucas (2 aprovações)")
    provider.marcar_visto("PLATZ-1")

    jira.gitea["status"] = "MERGED"
    t = ticket()
    checar("MR do Gitea mesclada vira novidade", t.novo and t.tipo_evento == "mr_mesclada")
    provider.marcar_visto("PLATZ-1")

    jira.gitlab["commentCount"] = 3
    checar("comentário novo na MR vira novidade", ticket().tipo_evento == "mr_comentario")
    provider.marcar_visto("PLATZ-1")

    jira.falhar = True
    t = ticket()
    checar("falha no painel de desenvolvimento não inventa evento nem derruba o ticket", not t.novo and t.mrs == [])
    jira.falhar = False

    estado = persistencia.obter_estado_ticket("PLATZ-1")
    estado.pop("mrs")
    persistencia.salvar_estado_ticket("PLATZ-1", estado)
    checar("estado antigo sem MRs não dispara aprovações antigas", not ticket().novo)
    checar("estado antigo ganha linha de base das MRs", persistencia.obter_estado_ticket("PLATZ-1").get("mrs") is not None)
    jira.gitlab["reviewers"].append({"name": "Paula", "approved": True})
    t = ticket()
    checar("depois da linha de base, aprovação nova conta", t.tipo_evento == "mr_aprovada"
           and t.detalhe_evento == "aprovada por Paula (3 aprovações)")

    print(f"\n{len(falhas)} falha(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
