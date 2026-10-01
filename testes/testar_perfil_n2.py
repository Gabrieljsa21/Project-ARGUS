"""Validação offline do perfil N2 (2026-10-01, ver docs/ARQUITETURA.md "Perfil
N1/N2") - sem rede: `JiraProvider` montado sem `__init__` e com `_obter`
substituído por respostas fixas. Confirma leitura do perfil (config > .env >
N1), categorias por projeto, SLA/campos/N1 vindos do NSD de origem, novidade
por comentário no NSD e o menu de Configurações gravando o perfil sem apagar
as outras opções. Rodar a partir da raiz do projeto:

    QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe testes/testar_perfil_n2.py
"""

import os
import sys
import tempfile

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from argus.core.widget import ArgusWidget, _DialogoConfiguracoes, salvar_configuracoes_do_dialogo
from argus.persistencia import PersistenciaArquivo
from argus.providers.jira_provider import JiraProvider

MINHA_CONTA = "eu"
CONTA_N1 = "n1"


def _comentario(id_, conta, nome):
    return {"id": id_, "author": {"accountId": conta, "displayName": nome}, "body": None, "created": f"2026-10-01T10:0{id_}"}


def _issue(chave, status, links=(), comentarios=(), assignee=None, empresa=None):
    return {"key": chave, "fields": {
        "summary": f"Resumo {chave}", "status": {"name": status}, "priority": {"name": "Medium"},
        "updated": "2026-10-01", "assignee": assignee, "reporter": None, "description": None,
        "attachment": [], "comment": {"comments": list(comentarios)},
        "issuelinks": [{"type": {"name": "Problem/Incident"}, "outwardIssue": {"key": k}} for k in links],
        "customfield_14601": {"value": empresa} if empresa else None,
    }}


class _JiraFalso:
    def __init__(self):
        self.nsd = _issue("NSD-1", "Aguardando desenvolvimento", links=["PLATZ-1"],
                          assignee={"accountId": CONTA_N1, "displayName": "Pessoa N1"}, empresa="Cliente X")
        self.dev = _issue("PLATZ-1", "Code Review", links=["NSD-1"])
        self.sem_origem = _issue("PLATZ-2", "Pronto")
        self.fora_do_board = _issue("BAHN-3", "Aberto")

    def obter(self, caminho, params=None, tentativas=3):
        if caminho == "/rest/api/3/search/jql":
            jql = params["jql"]
            if "project in (PLATZ, BAHN)" not in jql:
                return {"issues": []}  # JQL do perfil N1
            if "status in (13157)" in jql:
                return {"issues": [self.dev]}
            if "status in (13155, 4, 13154)" in jql:
                return {"issues": [self.sem_origem]}
            if "status not in" in jql:
                return {"issues": [self.fora_do_board]}
            return {"issues": []}
        if caminho == "/rest/servicedeskapi/request/NSD-1/sla":
            return {"values": [{"name": "Time to resolution", "ongoingCycle": {
                "breached": False, "remainingTime": {"millis": 3_600_000, "friendly": "1h"}}}]}
        if caminho.startswith("/rest/servicedeskapi/"):
            raise AssertionError(f"SLA não deveria ser buscado em {caminho}")
        chave = caminho.rsplit("/", 1)[-1]
        return {"NSD-1": self.nsd, "PLATZ-1": self.dev, "PLATZ-2": self.sem_origem, "BAHN-3": self.fora_do_board}[chave]


def _provider(persistencia, jira):
    provider = JiraProvider.__new__(JiraProvider)
    provider._base_url = "https://example.atlassian.net"
    provider._persistencia = persistencia
    provider._persistencia_configuracoes = persistencia
    provider._descrever_imagem = None
    provider._minha_account_id = MINHA_CONTA
    provider._obter = jira.obter
    return provider


def main():
    caminho = os.path.join(tempfile.gettempdir(), "argus_teste_perfil_n2.json")
    if os.path.exists(caminho):
        os.remove(caminho)
    persistencia = PersistenciaArquivo(caminho)
    jira = _JiraFalso()
    provider = _provider(persistencia, jira)
    falhas = []

    def checar(descricao, ok):
        print(("OK: " if ok else "FALHA: ") + descricao)
        if not ok:
            falhas.append(descricao)

    os.environ.pop("ARGUS_PERFIL", None)
    checar("padrão sem config nem .env é N1", provider.perfil == "n1")
    os.environ["ARGUS_PERFIL"] = "n2"
    checar(".env vale sem config salva", provider.perfil == "n2")
    persistencia.salvar_configuracoes({"perfil": "n1"})
    checar("config salva prevalece sobre o .env", provider.perfil == "n1")
    os.environ.pop("ARGUS_PERFIL", None)

    persistencia.salvar_configuracoes({"perfil": "n2"})
    categorias = provider.listar_categorias()
    por_nome = {c.nome_exibicao: c for c in categorias}
    checar("categorias = colunas do board + Outros", list(por_nome) == [
        "Disponível", "Em Andamento", "Em Revisão", "Em Publicação", "Em Validação", "Impedido", "Outros"])
    checar("PLATZ e BAHN juntos por status", [t.chave for t in por_nome["Em Revisão"].tickets] == ["PLATZ-1"]
           and [t.chave for t in por_nome["Disponível"].tickets] == ["PLATZ-2"])
    checar("status fora do board cai em Outros", [t.chave for t in por_nome["Outros"].tickets] == ["BAHN-3"])
    checar("status na linha só onde a coluna junta vários", por_nome["Disponível"].mostrar_status_na_lista
           and por_nome["Outros"].mostrar_status_na_lista and not por_nome["Em Revisão"].mostrar_status_na_lista)
    platz = {t.chave: t for c in categorias for t in c.tickets}
    dev = platz["PLATZ-1"]
    checar("SLA vem do NSD de origem", dev.sla_texto == "1h")
    checar("chamado de origem preenchido", dev.chamado_origem == "NSD-1" and dev.chamado_origem_url.endswith("/browse/NSD-1"))
    checar("N1 = responsável do NSD", dev.n1_responsavel == "Pessoa N1")
    checar("empresa completada pelo NSD", dev.empresa == "Cliente X")
    checar("ticket fora do suporte aparece, sem SLA", platz["PLATZ-2"].sla_texto == "" and platz["PLATZ-2"].chamado_origem == "")

    provider.marcar_visto("PLATZ-1")
    checar("visto limpa a novidade", not _ticket(provider, "PLATZ-1").novo)

    jira.nsd["fields"]["comment"]["comments"].append(_comentario(1, MINHA_CONTA, "Eu"))
    checar("comentário próprio no NSD não conta", not _ticket(provider, "PLATZ-1").novo)
    jira.nsd["fields"]["comment"]["comments"].append(_comentario(2, CONTA_N1, "Pessoa N1"))
    novo = _ticket(provider, "PLATZ-1")
    checar("comentário do N1/cliente no NSD conta como novidade", novo.novo and novo.tipo_evento == "comentario")

    persistencia.salvar_configuracoes({"perfil": "n1", "limite_janelas_destacadas": 7})
    checar("perfil N1 volta às categorias por status", [c.chave for c in provider.listar_categorias()] == ["em_revisao", "atendimento", "cliente", "dev"])

    app = QApplication(sys.argv)
    widget = ArgusWidget(provider, persistencia)
    widget._tarefa_atualizacao.wait()
    app.processEvents()
    app.processEvents()
    dialogo = _DialogoConfiguracoes(7, False, perfil_n2=False, parent=widget)
    dialogo._campo_perfil.setChecked(True)
    dialogo._confirmar()
    checar("dialog devolve perfil N2", dialogo.perfil_n2 is True)
    sem_perfil = _DialogoConfiguracoes(7, False, parent=widget)
    checar("provider sem perfil não mostra o card", not hasattr(sem_perfil, "_campo_perfil"))

    # Tela nativa aberta por fora do widget (como a GAIA faz) - sem parent.
    persistencia.salvar_configuracoes({"perfil": "n1", "limite_janelas_destacadas": 7, "opcao_da_gaia": "x"})
    sem_widget = _DialogoConfiguracoes(7, False, perfil_n2=False)
    sem_widget._campo_perfil.setChecked(True)
    sem_widget._confirmar()
    salvo = salvar_configuracoes_do_dialogo(persistencia, sem_widget)
    checar("tela sem widget grava o perfil", persistencia.obter_configuracoes().get("perfil") == "n2")
    checar("salvar mescla e mantém opção desconhecida", salvo.get("opcao_da_gaia") == "x")

    widget.atualizar()
    widget._tarefa_atualizacao.wait()
    app.processEvents()
    app.processEvents()
    checar("widget registra o perfil exibido", widget._perfil_exibido == "n2")
    recarregou = []
    widget.atualizar = lambda: recarregou.append(True)
    widget.aplicar_configuracoes({"perfil": "n2", "chacoalhada_ativa": True})
    checar("mesmo perfil não recarrega, mas aplica o resto", not recarregou and widget._chacoalhada_ativa is True)
    widget.aplicar_configuracoes({"perfil": "n1"})
    checar("perfil diferente recarrega a lista", recarregou == [True])

    print(f"\n{len(falhas)} falha(s)")
    return 1 if falhas else 0


def _ticket(provider, chave):
    return next(t for c in provider.listar_categorias() for t in c.tickets if t.chave == chave)


if __name__ == "__main__":
    sys.exit(main())
