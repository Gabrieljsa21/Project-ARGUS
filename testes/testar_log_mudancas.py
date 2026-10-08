"""Validação offline do log de mudanças do botão "Log" (2026-10-08, ver
docs/ARQUITETURA.md "Log de mudanças") - sem rede: `JiraProvider` montado sem
`__init__` e com `_obter` respondendo um ticket falso que muda entre os ciclos.
Confirma que o log lista TODAS as mudanças desde o último visto (não só o
motivo principal do aviso), que sobrevive ao `marcar_visto` e que estado
antigo, sem os campos novos, não quebra. Rodar a partir da raiz do projeto:

    .venv/Scripts/python.exe testes/testar_log_mudancas.py
"""

import os
import sys
import tempfile

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from argus.persistencia import PersistenciaArquivo
from argus.providers.jira_provider import JiraProvider


def _comentario(id_, autor_id, autor_nome, texto):
    return {"id": id_, "author": {"accountId": autor_id, "displayName": autor_nome},
            "body": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": texto}]}]}}


class _JiraFalso:
    def __init__(self):
        self.status = "Code Review"
        self.prioridade = "Medium"
        self.assignee = None
        self.comentarios = []
        self.mr = {"id": "bringitbr/platz/platz.core!10", "name": "Corrige X", "status": "OPEN",
                   "url": "https://gitlab.com/mr/10", "commentCount": 0, "repositoryName": "platz.core",
                   "reviewers": [{"name": "Rafael", "approved": False}]}

    def _issue(self):
        return {"key": "PLATZ-1", "id": "100", "fields": {
            "summary": "Resumo", "status": {"name": self.status}, "priority": {"name": self.prioridade},
            "updated": "2026-10-08", "assignee": self.assignee, "reporter": None, "description": None,
            "attachment": [], "comment": {"comments": list(self.comentarios)}, "issuelinks": [],
        }}

    def obter(self, caminho, params=None, tentativas=3):
        if caminho == "/rest/api/3/search/jql":
            return {"issues": [self._issue()] if "status in (13157)" in params["jql"] else []}
        if caminho.startswith("/rest/dev-status/"):
            if caminho.endswith("/summary"):
                return {"summary": {"pullrequest": {"byInstanceType": {"oAuth-gitlab": {"count": 1}}}}}
            return {"detail": [{"pullRequests": [dict(self.mr, reviewers=[dict(r) for r in self.mr["reviewers"]])]}]}
        if caminho.startswith("/rest/servicedeskapi/"):
            raise requests.HTTPError("sem SLA")
        if params and params.get("expand") == "changelog":
            return {"changelog": {"histories": [{"author": {"accountId": "outro"}, "items": [{"field": "status"}]}]}}
        return self._issue()


def main():
    caminho = os.path.join(tempfile.gettempdir(), "argus_teste_log_mudancas.json")
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

    def checar(descricao, ok, detalhe=None):
        print(("OK: " if ok else "FALHA: ") + descricao)
        if not ok:
            falhas.append(descricao)
            if detalhe is not None:
                print(f"    obtido: {detalhe}")

    def ticket():
        return next(t for c in provider.listar_categorias() for t in c.tickets if t.chave == "PLATZ-1")

    t = ticket()
    checar("ticket nunca visto: log diz que é novo", t.novo and t.mudancas == ["Ticket novo na sua fila"], t.mudancas)
    checar("pendente não tem data de visto", t.mudancas_vistas_em == "")

    provider.marcar_visto("PLATZ-1")
    t = ticket()
    checar("depois de visto, o log do último aviso continua disponível",
           not t.novo and t.mudancas == ["Ticket novo na sua fila"] and t.mudancas_vistas_em, t.mudancas)

    # Várias mudanças de uma vez: o aviso é só "status_mudou", o log lista tudo.
    jira.status = "Done"
    jira.assignee = {"accountId": "fulano", "displayName": "Fulano"}
    jira.mr["reviewers"][0]["approved"] = True
    jira.mr["commentCount"] = 2
    jira.comentarios.append(_comentario("1", "cliente", "Cliente X", "Ainda está dando erro na integração"))
    t = ticket()
    esperado = [
        "Status: Code Review → Done",
        "Responsável: ninguém → Fulano",
        "MR platz.core!10 aprovada por Rafael",
        "MR platz.core!10: 2 comentários novos",
        'Comentário novo de Cliente X no PLATZ-1 (N2): "Ainda está dando erro na integração"',
    ]
    checar("aviso continua sendo o motivo principal", t.tipo_evento == "status_mudou")
    checar("log lista todas as mudanças, na ordem de importância", t.mudancas == esperado, t.mudancas)

    provider.marcar_visto("PLATZ-1")
    t = ticket()
    checar("log das mudanças sobrevive ao marcar_visto", not t.novo and t.mudancas == esperado, t.mudancas)

    provider.marcar_visto("PLATZ-1")
    checar("visto de novo sem mudança mantém o último log", ticket().mudancas == esperado)

    jira.comentarios.append(_comentario("2", "eu", "Eu", "Respondi"))
    t = ticket()
    checar("comentário próprio não gera aviso nem entra no log", not t.novo and t.mudancas == esperado, t.mudancas)

    jira.mr["status"] = "MERGED"
    checar("MR mesclada aparece com o status legível", ticket().mudancas == ["MR platz.core!10: Mesclada"])
    provider.marcar_visto("PLATZ-1")

    # Estado gravado antes deste recurso: sem nome do responsável nem trecho.
    estado = persistencia.obter_estado_ticket("PLATZ-1")
    for campo in ("assignee_nome", "ultimo_comentario_trecho", "ultimas_mudancas"):
        estado.pop(campo, None)
    persistencia.salvar_estado_ticket("PLATZ-1", estado)
    checar("estado antigo sem log não quebra", ticket().mudancas == [])
    jira.assignee = {"accountId": "beltrano", "displayName": "Beltrano"}
    t = ticket()
    checar("estado antigo sem nome do responsável usa texto genérico",
           t.mudancas == ["Responsável alterado para Beltrano"], t.mudancas)

    jira.comentarios.append(_comentario("3", "cliente", "Cliente X", "x" * 300))
    trecho = next(m for m in ticket().mudancas if m.startswith("Comentário"))
    checar("comentário longo é cortado", trecho.endswith('..."') and len(trecho) < 220, trecho)

    # Perfil N2: comentário no chamado de origem sai marcado como N1, com a chave.
    visto = {"status": "A", "prioridade": "Medium", "assignee_id": None, "chave": "PLATZ-1",
             "origem_ultimo_comentario_id": "1"}
    atual = dict(visto, assignee_nome="", origem_chave="BSD-9", origem_ultimo_comentario_id="2",
                 origem_ultimo_comentario_autor_id="n1", origem_ultimo_comentario_autor_nome="Ana",
                 origem_ultimo_comentario_trecho="Cliente confirmou")
    checar("comentário do chamado de origem marcado como N1",
           provider._descrever_mudancas(visto, atual) == ['Comentário novo de Ana no BSD-9 (N1): "Cliente confirmou"'],
           provider._descrever_mudancas(visto, atual))
    checar("NSD, BSD e NPSD contam como chamado de atendimento (N1)",
           all(JiraProvider._eh_chamado_atendimento(c) for c in ("NSD-1", "BSD-2", "NPSD-3"))
           and not any(JiraProvider._eh_chamado_atendimento(c) for c in ("PLATZ-1", "BAHN-2", "NSDX-3")))

    print(f"\n{len(falhas)} falha(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
