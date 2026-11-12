"""Testes de unidade (pytest) das melhorias de 2026-11-12, sem rede e sem Qt:
persistência atômica e poda, urgência por palavra inteira, máscara, paginação
da busca, falhas visíveis e id da conta buscado depois. Rodar da raiz:

    .venv/Scripts/python.exe -m pytest
"""

import json
import os
from datetime import datetime, timedelta

import pytest
import requests

from argus.modelos import PERFIL_N1
from argus.persistencia import CAMPO_SALVO_EM, PersistenciaArquivo
from argus.pontuacao import detectar_urgencia_no_texto
from argus.providers.jira_provider import JiraProvider
from argus.seguranca import mascarar


# --- persistência -----------------------------------------------------------

def test_gravacao_atomica_nao_deixa_temporario(tmp_path):
    caminho = tmp_path / "config.json"
    persistencia = PersistenciaArquivo(str(caminho))
    persistencia.salvar_estado_ticket("NSD-1", {"status": "A"})
    assert not (tmp_path / "config.json.tmp").exists()
    estado = persistencia.obter_estado_ticket("NSD-1")
    assert estado["status"] == "A" and CAMPO_SALVO_EM in estado


def test_arquivo_ilegivel_e_guardado_a_parte(tmp_path):
    caminho = tmp_path / "config.json"
    caminho.write_text('{"tickets": {"NSD-1": ', encoding="utf-8")
    persistencia = PersistenciaArquivo(str(caminho))
    assert persistencia.obter_estado_ticket("NSD-1") is None
    guardados = [p for p in os.listdir(tmp_path) if ".corrompido-" in p]
    assert len(guardados) == 1
    assert (tmp_path / guardados[0]).read_text(encoding="utf-8").startswith('{"tickets"')


def test_poda_remove_estado_antigo_e_analise_orfa(tmp_path):
    caminho = tmp_path / "config.json"
    antigo = (datetime.now() - timedelta(days=200)).isoformat(timespec="seconds")
    recente = datetime.now().isoformat(timespec="seconds")
    caminho.write_text(json.dumps({
        "tickets": {
            "NSD-1": {"status": "A", CAMPO_SALVO_EM: antigo},
            "NSD-2": {"status": "B", CAMPO_SALVO_EM: recente},
            "NSD-3": {"status": "C"},
        },
        "analises_imagem": {"NSD-1:10": "print velho", "NSD-2:11": "print novo"},
        "posicao_janela": [1, 2],
    }), encoding="utf-8")
    persistencia = PersistenciaArquivo(str(caminho))
    assert persistencia.obter_estado_ticket("NSD-1") is None
    assert persistencia.obter_estado_ticket("NSD-2")["status"] == "B"
    # Estado sem data ganha a de hoje, em vez de sumir.
    assert CAMPO_SALVO_EM in persistencia.obter_estado_ticket("NSD-3")
    assert persistencia.obter_analise_imagem("NSD-1:10") is None
    assert persistencia.obter_analise_imagem("NSD-2:11") == "print novo"
    assert persistencia.obter_posicao_janela() == (1, 2)


# --- urgência e máscara -----------------------------------------------------

@pytest.mark.parametrize("texto, urgente", [
    ("URGÊNCIA total", True),
    ("Sistema parado desde cedo", True),
    ("preciso disso imediatamente!", True),
    ("não é urgente, mas paramos de vender", True),
    ("foi comparado com o relatório de ontem", False),
    ("pedido separado em duas notas", False),
    ("e-mail disparado para o cliente", False),
    ("nao e urgente", False),
    ("Sem urgência nenhuma", False),
])
def test_urgencia_por_palavra_inteira_e_sem_acento(texto, urgente):
    assert detectar_urgencia_no_texto(texto) is urgente


@pytest.mark.parametrize("texto, esperado", [
    ("senha errada no login", "senha errada no login"),
    ("o token expirou ontem", "o token expirou ontem"),
    ("senha: abc123 não funciona", "[senha ou token removido] não funciona"),
    ("api_key=xyz987", "[senha ou token removido]"),
    ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc", "Authorization: [senha ou token removido]"),
    ("CPF 123.456.789-09 cadastrado", "CPF [CPF removido] cadastrado"),
])
def test_mascara_sem_engolir_texto_comum(texto, esperado):
    assert mascarar(texto) == esperado


# --- provider sem rede ------------------------------------------------------

def _provider(tmp_path, obter):
    persistencia = PersistenciaArquivo(str(tmp_path / "config.json"))
    persistencia.salvar_configuracoes({"perfil": PERFIL_N1})
    provider = JiraProvider.__new__(JiraProvider)
    provider._base_url = "https://example.atlassian.net"
    provider._persistencia = persistencia
    provider._persistencia_configuracoes = persistencia
    provider._descrever_imagem = None
    provider._minha_account_id = "eu"
    provider._obter = obter
    return provider


def _issue(chave):
    return {"key": chave, "id": chave.split("-")[1], "fields": {
        "summary": "Resumo", "status": {"name": "Aguardando Atendimento"}, "priority": {"name": "Medium"},
        "updated": "2026-11-12", "assignee": None, "reporter": None, "description": None,
        "attachment": [], "comment": {"comments": []}, "issuelinks": [], "labels": [],
    }}


def _erro_http(status):
    resposta = requests.Response()
    resposta.status_code = status
    return requests.HTTPError(f"{status} Client Error", response=resposta)


def _respostas_comuns(caminho, params):
    if caminho.startswith("/rest/servicedeskapi/"):
        raise requests.HTTPError("sem SLA")
    if caminho.startswith("/rest/dev-status/"):
        return {"summary": {}}
    raise AssertionError(f"caminho inesperado: {caminho}")


def test_busca_segue_todas_as_paginas(tmp_path):
    def obter(caminho, params=None, tentativas=3):
        if caminho == "/rest/api/3/search/jql":
            if "status = 10103" not in params["jql"]:
                return {"issues": []}
            if params.get("nextPageToken") is None:
                return {"issues": [_issue(f"NSD-{i}") for i in range(1, 101)], "nextPageToken": "p2"}
            return {"issues": [_issue("NSD-101")], "isLast": True}
        return _respostas_comuns(caminho, params)

    provider = _provider(tmp_path, obter)
    categorias = {c.chave: c for c in provider.listar_categorias()}
    assert len(categorias["atendimento"].tickets) == 101
    assert provider.falhas_ultima_busca == []


def test_falha_parcial_fica_registrada_e_o_resto_aparece(tmp_path):
    def obter(caminho, params=None, tentativas=3):
        if caminho == "/rest/api/3/search/jql":
            if "status = 10104" in params["jql"]:
                raise requests.ConnectionError("rede caiu")
            return {"issues": [_issue("NSD-1")] if "status = 10103" in params["jql"] else []}
        return _respostas_comuns(caminho, params)

    provider = _provider(tmp_path, obter)
    categorias = {c.chave: c for c in provider.listar_categorias()}
    assert "cliente" not in categorias
    assert [t.chave for t in categorias["atendimento"].tickets] == ["NSD-1"]
    assert len(provider.falhas_ultima_busca) == 1 and "Aguardando Cliente" in provider.falhas_ultima_busca[0]


def test_credencial_recusada_sobe_na_hora(tmp_path):
    def obter(caminho, params=None, tentativas=3):
        raise _erro_http(401)

    with pytest.raises(requests.HTTPError):
        _provider(tmp_path, obter).listar_categorias()


def test_todas_as_categorias_falhando_sobe_o_erro(tmp_path):
    def obter(caminho, params=None, tentativas=3):
        raise requests.Timeout("lento demais")

    with pytest.raises(requests.Timeout):
        _provider(tmp_path, obter).listar_categorias()


def test_id_da_conta_buscado_depois_se_a_rede_falhar_ao_abrir(tmp_path):
    chamadas = []

    def obter(caminho, params=None, tentativas=3):
        chamadas.append(caminho)
        if caminho == "/rest/api/3/myself":
            return {"accountId": "eu"}
        if caminho == "/rest/api/3/search/jql":
            return {"issues": []}
        return _respostas_comuns(caminho, params)

    provider = _provider(tmp_path, obter)
    provider._minha_account_id = None
    provider.listar_categorias()
    assert provider._minha_account_id == "eu" and chamadas[0] == "/rest/api/3/myself"


def test_detalhes_completos_saem_mascarados(tmp_path):
    issue = _issue("NSD-1")
    issue["fields"]["description"] = {"type": "doc", "content": [{"type": "text", "text": "senha: abc123"}]}
    issue["fields"]["comment"]["comments"] = [{
        "id": "1", "created": "2026-11-12", "author": {"accountId": "cliente", "displayName": "Cliente"},
        "body": {"type": "doc", "content": [{"type": "text", "text": "meu CPF 123.456.789-09"}]},
    }]

    def obter(caminho, params=None, tentativas=3):
        return issue

    detalhes = _provider(tmp_path, obter).obter_detalhes_completos("NSD-1")
    assert "abc123" not in detalhes["descricao"]
    assert "123.456.789-09" not in detalhes["comentarios"][0]["texto"]
