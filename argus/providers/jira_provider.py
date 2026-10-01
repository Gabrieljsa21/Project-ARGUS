"""Fonte de notificação real - Jira Cloud REST API v3, Basic Auth (e-mail +
API token, não senha). Dois perfis (ver `JiraProvider.perfil` e
docs/ARQUITETURA.md "Perfil N1/N2"):
- N1: fluxo de atendimento (assignee = você mesmo), nos 4 status do NSD -
  "Em Revisão", "Aguardando atendimento", "Aguardando cliente" e "Aguardando
  desenvolvimento".
- N2: tickets de desenvolvimento PLATZ/BAHN atribuídos a você, uma categoria
  por projeto, com SLA/comentários/N1 lidos do chamado NSD de origem.

Heurística de novidade (validada com o usuário, ver docs/ARQUITETURA.md): conta como
novo desde a última vez que o ticket foi ABERTO (não desde a última checagem) -
mudança de status, de prioridade, de responsável, ou comentário de alguém que
não seja o próprio usuário nem uma conta de automação. Comentário automático do
Jira (ex.: aviso de SLA de "Automation for Jira") é ruído, ignorado de propósito.

Vínculo de 2 saltos (categoria "Aguardando desenvolvimento"): quando o ticket
tem um link tipo "Problem/Incident" pro board de dev, a novidade é checada no
ticket VINCULADO, não no ticket de atendimento em si - os devs só comentam lá.
Isso vale pra qualquer ticket com esse vínculo, não só os "Aguardando
desenvolvimento" - a categoria em si não importa pra essa decisão, só o vínculo.

🔥 JQL usa o ID do status, não o nome (2026-08-14, achado testando contra a
instância real) - `status = "Aguardando atendimento"` por NOME devolvia lista
vazia mesmo pra um ticket comprovadamente nesse status, porque a mesma string
de nome existe (ou quase - "Em revisão" minúsculo vs "Em Revisão" com R
maiúsculo) em workflows de OUTROS projetos com IDs diferentes, e o Jira não
resolve isso de forma confiável por nome. IDs abaixo confirmados direto contra
`/rest/api/3/project/NSD/statuses` - só valem PRA ESTE projeto (NSD); mudariam
se um dia o fluxo for replicado em outro projeto Jira."""

import os
import time
from typing import Callable

import requests

from ..modelos import PERFIL_N1, PERFIL_N2, Categoria, Ticket
from ..persistencia import Persistencia
from ..pontuacao import calcular_detalhamento_pontuacao, detectar_urgencia_no_texto
from ..seguranca import mascarar
from .base import NotificacaoProvider

CATEGORIAS_STATUS = [
    ("em_revisao", "Em Revisão", 10101),
    ("atendimento", "Aguardando Atendimento", 10103),
    ("cliente", "Aguardando Cliente", 10104),
    ("dev", "Aguardando Desenvolvimento", 10300),
]

# 🔥 Perfil N2 (2026-10-01, pedido do usuário: "agora eu virei dev... os
# tickets q o suporte n1 me manda, ja q sou o n2, cai em 2 boards diferentes")
# - o N1 continua dono do chamado NSD; a automação cria o ticket de dev
# (PLATZ/BAHN, boards 462/375) e ele é atribuído ao N2. Uma categoria por
# PROJETO (escolha do usuário), com tudo que está atribuído e não concluído -
# inclusive ticket sem origem no suporte (ex.: "Nova função" de backlog).
PERFIL_PADRAO = PERFIL_N1
CATEGORIAS_PROJETO_N2 = [
    ("platz", "Platz", "PLATZ"),
    ("bahn", "Bahn", "BAHN"),
]
CHAVES_CATEGORIAS_N2 = {chave for chave, _, _ in CATEGORIAS_PROJETO_N2}
PROJETO_ATENDIMENTO = "NSD"

TIPO_VINCULO_DEV = "Problem/Incident"
AUTORES_AUTOMATICOS_IGNORADOS = {"Automation for Jira"}
# 🔥 Campos extras pro painel de detalhes (2026-08-15, pedido do usuário: "com
# as informações mais detalhadas do ticket... plataforma, organizations,
# relator, responsavel, tipo de solicitação") - IDs confirmados direto contra
# a instância real (`nordwareservices.atlassian.net`, projeto NSD) via MCP
# Atlassian, mesmo processo já usado pros status (ver docstring do módulo):
# customfield_14901 = "Plataforma", customfield_14601 = "Empresa",
# customfield_10007 = objeto de request do JSM (`.requestType.name` é o "Tipo
# de solicitação"). `reporter` é o "Relator" nativo do Jira.
CAMPO_PLATAFORMA = "customfield_14901"
CAMPO_EMPRESA = "customfield_14601"
CAMPO_TIPO_SOLICITACAO = "customfield_10007"
# 🔥 description/attachment adicionados (2026-08-15) - antes só bastava pra
# mostrar o ticket, agora a descrição/comentário/print alimentam a pontuação de
# foco (ver pontuacao.py) e a detecção de urgência no texto livre.
CAMPOS_ISSUE = (
    "summary,status,priority,updated,assignee,reporter,comment,issuelinks,"
    f"description,attachment,{CAMPO_PLATAFORMA},{CAMPO_EMPRESA},{CAMPO_TIPO_SOLICITACAO}"
)

# 🔥 Prioridades que contam como "crítico" pra fala da GAIA (2026-08-15,
# pedido do usuário: "critico pode considerar high tbm") - nomes reais do
# esquema de prioridade padrão do Jira ("Highest"/"High"), não confirmados
# como existentes de fato neste projeto (só "High"/"Medium"/"Low"/"Lowest"
# foram vistos em tickets reais até agora) - ajustar se "Highest" nunca
# aparecer na prática.
PRIORIDADES_CRITICAS = {"Highest", "High"}


class JiraProvider(NotificacaoProvider):
    def __init__(
        self, base_url: str, email: str, api_token: str, persistencia: Persistencia,
        descrever_imagem: Callable[[bytes], str] | None = None,
        persistencia_configuracoes: Persistencia | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._auth = (email, api_token)
        self._persistencia = persistencia
        # 🔥 De onde ler o perfil N1/N2 (2026-10-01) - por padrão a própria
        # persistência do provider. A GAIA cria um provider de VOZ com
        # persistência separada (`data/jira_voz_visto.json`), que nunca recebe
        # as configurações do menu - ela passa aqui a persistência padrão do
        # widget pra que voz e widget sigam sempre o MESMO perfil.
        self._persistencia_configuracoes = persistencia_configuracoes or persistencia
        # 🔥 Gancho OPCIONAL de visão (2026-08-15) - o Argus em si não tem
        # dependência de LLM nenhuma (fica leve/usável standalone pelos colegas,
        # sem exigir chave de IA). Quem quiser analisar print sem descrição
        # (ver `_obter_texto_para_analise`) injeta essa função (ex.: a GAIA,
        # com o `client_vision` dela já configurado); sem isso, o ticket só-print
        # simplesmente não ganha pontuação extra de urgência por texto.
        self._descrever_imagem = descrever_imagem
        self._minha_account_id = self._obter_meu_account_id()

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def perfil(self) -> str:
        """Lido a CADA busca (não guardado no `__init__`) - trocar o perfil no
        menu de Configurações vale no próximo ciclo, inclusive pro provider
        de voz da GAIA, sem reiniciar nada. Ordem: config salva pelo menu >
        `ARGUS_PERFIL` no `.env` > N1 (comportamento original, padrão pros
        colegas que só fazem atendimento)."""
        perfil = self._persistencia_configuracoes.obter_configuracoes().get("perfil")
        perfil = perfil or os.environ.get("ARGUS_PERFIL", PERFIL_PADRAO)
        return perfil if perfil in (PERFIL_N1, PERFIL_N2) else PERFIL_PADRAO

    def _definicao_categorias(self) -> list:
        """(chave, nome de exibição, JQL) de cada categoria do perfil atual."""
        if self.perfil == PERFIL_N2:
            return [
                (chave, nome, f"project = {projeto} AND assignee = currentUser() "
                              "AND statusCategory != Done ORDER BY updated DESC")
                for chave, nome, projeto in CATEGORIAS_PROJETO_N2
            ]
        return [
            (chave, nome, f"assignee = currentUser() AND status = {id_status} ORDER BY updated DESC")
            for chave, nome, id_status in CATEGORIAS_STATUS
        ]

    @staticmethod
    def _eh_chamado_atendimento(chave: str) -> bool:
        return chave.startswith(f"{PROJETO_ATENDIMENTO}-")

    def _obter(self, caminho: str, params: dict | None = None, tentativas: int = 3) -> dict:
        """🔥 Retentativa em timeout/conexão (2026-08-23, achado em uso real:
        `nordwareservices.atlassian.net` engasga de forma transitória - visto
        repetidas vezes nesta mesma investigação, sempre resolvendo sozinho
        numa segunda tentativa, inclusive no PRÓPRIO `/rest/api/3/myself`
        chamado no `__init__` - uma falha aí derrubava a abertura do Argus
        inteira, antes mesmo de chegar em qualquer outro fix de resiliência
        já feito em `buscar_dados_brutos`/`ArgusWidget.atualizar`). Só
        retenta erro de CONEXÃO/timeout (`ConnectionError`/`Timeout` - cobre
        `ConnectTimeout`, que herda de ambos) - um erro HTTP de verdade (401
        credencial errada, 404 issue não existe) não muda tentando de novo,
        então sobe na hora, sem esperar."""
        ultimo_erro = None
        for tentativa in range(1, tentativas + 1):
            try:
                resposta = requests.get(f"{self._base_url}{caminho}", auth=self._auth, params=params, timeout=15)
                resposta.raise_for_status()
                return resposta.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                ultimo_erro = e
                if tentativa < tentativas:
                    time.sleep(2)
        raise ultimo_erro

    def _obter_meu_account_id(self) -> str:
        return self._obter("/rest/api/3/myself")["accountId"]

    def _buscar_issues(self, jql: str) -> list:
        """`/rest/api/3/search` (clássico) foi descontinuado pela Atlassian -
        devolve 410 Gone. `/rest/api/3/search/jql` é o substituto oficial,
        paginado por `nextPageToken` em vez de `startAt`/`total`."""
        dados = self._obter("/rest/api/3/search/jql", params={
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

    def _chamado_origem(self, issue: dict) -> dict | None:
        """Lado inverso do vínculo de 2 saltos (perfil N2): partindo do ticket
        de dev, o chamado NSD que o originou. Filtra pelo PROJETO além do tipo
        de vínculo porque um ticket de dev pode ter outros "Problem/Incident"
        entre si. Vários NSDs do mesmo problema podem apontar pro mesmo
        ticket de dev - usa o primeiro (o que a automação criou junto)."""
        for vinculo in issue["fields"].get("issuelinks", []):
            if vinculo["type"]["name"] != TIPO_VINCULO_DEV:
                continue
            vinculado = vinculo.get("inwardIssue") or vinculo.get("outwardIssue")
            if vinculado and self._eh_chamado_atendimento(vinculado["key"]):
                return vinculado
        return None

    def _resolver_estado_novidade(self, issue: dict) -> tuple:
        """(estado atual pra comparar com o `visto`, issue NSD de origem ou
        None). Decide pela CHAVE do ticket, não pelo perfil ativo - assim
        `marcar_visto` grava o mesmo formato de estado que a busca compara,
        mesmo se o perfil for trocado entre as duas chamadas.

        - Chamado NSD (perfil N1): comportamento original, novidade checada
          no ticket de dev vinculado, se houver.
        - Ticket de dev (perfil N2): novidade no PRÓPRIO ticket + último
          comentário do NSD de origem (pedido do usuário: comentário do
          cliente/N1 no NSD também conta como novidade pro N2)."""
        if self._eh_chamado_atendimento(issue["key"]):
            return self._estado_atual(self._resolver_issue_para_novidade(issue)), None
        atual = self._estado_atual(issue)
        vinculo = self._chamado_origem(issue)
        if vinculo is None:
            return atual, None
        origem = self._obter_issue_completo(vinculo["key"])
        comentarios_origem = origem["fields"].get("comment", {}).get("comments", [])
        ultimo = comentarios_origem[-1] if comentarios_origem else None
        atual.update({
            "origem_ultimo_comentario_id": ultimo["id"] if ultimo else None,
            "origem_ultimo_comentario_autor_id": ultimo["author"]["accountId"] if ultimo else None,
            "origem_ultimo_comentario_autor_nome": ultimo["author"].get("displayName", "") if ultimo else None,
        })
        return atual, origem

    def _eh_autor_automatico(self, nome_exibicao: str) -> bool:
        return nome_exibicao in AUTORES_AUTOMATICOS_IGNORADOS

    def _autor_ultima_mudanca_status(self, chave: str) -> str | None:
        """Account ID de quem fez a ÚLTIMA transição de status do ticket, via
        changelog do Jira (2026-08-21, pedido do usuário: "quando a mudança
        for apenas de status realizada por mim, não precisa notificar como
        novo, apenas atualizar o ticket para a coluna nova") - só chamado
        quando `_classificar_evento` já detectou que o status mudou desde o
        último `visto` (evento raro, não pesa no polling normal - diferente
        do SLA/pontuação de foco, que rodam pra TODO ticket a cada ciclo).
        `expand=changelog` devolve o histórico embutido no próprio issue -
        `histories` vem em ordem cronológica ASCENDENTE (mais antigo primeiro),
        por isso percorre de trás pra frente e para no primeiro item cujo
        campo é "status" (a transição mais recente)."""
        try:
            dados = self._obter(f"/rest/api/3/issue/{chave}", params={"fields": "status", "expand": "changelog"})
        except requests.HTTPError:
            return None
        for historia in reversed(dados.get("changelog", {}).get("histories", [])):
            for item in historia.get("items", []):
                if item.get("field") == "status":
                    return (historia.get("author") or {}).get("accountId")
        return None

    # --- pontuação de foco: texto livre (descrição/comentário/print) + SLA ---

    @staticmethod
    def _texto_plano_adf(no: dict | None) -> str:
        """Extrai só o texto puro de um nó ADF (Atlassian Document Format - é
        assim que `description`/corpo de comentário vêm na API v3, um documento
        rico em vez de string), varrendo recursivamente `content`. Não precisa
        de fidelidade nenhuma (não é pra reexibir, só pra mascarar/detectar
        urgência em cima) - só concatenar todo texto solto já basta."""
        if not no:
            return ""
        pedacos = []

        def _visitar(node):
            if isinstance(node, dict):
                if node.get("type") == "text":
                    pedacos.append(node.get("text", ""))
                for filho in node.get("content", []) or []:
                    _visitar(filho)
            elif isinstance(node, list):
                for item in node:
                    _visitar(item)

        _visitar(no)
        return " ".join(pedacos)

    def _obter_sla_info(self, chave: str) -> dict | None:
        """SLA REAL via Jira Service Management (`/rest/servicedeskapi/request/
        {chave}/sla`), não um `duedate` estimado - confirmado contra a instância
        real (2026-08-15) que esse endpoint responde pra este projeto. Usa
        especificamente "Time to resolution" (o prazo geral do chamado, não o
        de primeira resposta). Ticket sem SLA aplicável (ou já com o ciclo
        fechado) devolve None - a pontuação simplesmente não ganha esse bônus."""
        try:
            dados = self._obter(f"/rest/servicedeskapi/request/{chave}/sla")
        except requests.HTTPError:
            return None
        for metrica in dados.get("values", []):
            if metrica.get("name") != "Time to resolution":
                continue
            ciclo = metrica.get("ongoingCycle")
            if not ciclo:
                return None
            return {
                "breached": bool(ciclo.get("breached")),
                "restante_millis": ciclo.get("remainingTime", {}).get("millis", 0),
                # 🔥 String pronta do próprio Jira (2026-08-15, pro painel de
                # detalhes) - ex.: "5h 4m" - evita reimplementar formatação de
                # duração; o Jira já calcula isso considerando horário
                # comercial/pausas, que `restante_millis` sozinho não reflete.
                "restante_texto": ciclo.get("remainingTime", {}).get("friendly", ""),
            }
        return None

    def _ultimo_anexo_imagem(self, issue: dict) -> dict | None:
        """O ÚLTIMO anexo de imagem (não o primeiro) - a API do Jira lista
        anexos em ordem cronológica, e um ticket "Aguardando Cliente" pode
        acumular vários prints ao longo da conversa; o mais recente é o
        relevante pra analisar agora."""
        anexos_imagem = [
            a for a in issue["fields"].get("attachment", []) or []
            if (a.get("mimeType") or "").startswith("image/")
        ]
        return anexos_imagem[-1] if anexos_imagem else None

    def _baixar_anexo(self, url: str) -> bytes | None:
        try:
            resposta = requests.get(url, auth=self._auth, timeout=20)
            resposta.raise_for_status()
            return resposta.content
        except requests.RequestException:
            return None

    def _obter_texto_para_analise(self, issue: dict, chave: str) -> str:
        """Texto usado pra detectar urgência (ver pontuacao.py) - descrição +
        último comentário + descrição do último print anexado (via
        `self._descrever_imagem`, gancho opcional, ver __init__).

        🔥 A imagem é analisada SEMPRE que existe (2026-08-15, pedido do
        usuário: "ela tem de mandar a imagem independente se tem descrição ou
        não") - não só quando texto/comentário vêm vazios. Um chamado pode ter
        descrição escrita E um print que mostra o erro de verdade (o texto
        sozinho às vezes não conta a urgência real). Resultado é CACHEADO por
        anexo (`chave:id_do_anexo`, não só `chave`) - um print NOVO chegando
        depois (ticket que ganha um segundo anexo) não reaproveita a análise
        do anexo antigo; não chama visão de novo pro MESMO anexo a cada
        polling."""
        campos = issue["fields"]
        texto = self._texto_plano_adf(campos.get("description")).strip()
        comentarios = campos.get("comment", {}).get("comments", [])
        if comentarios:
            texto = f"{texto} {self._texto_plano_adf(comentarios[-1].get('body'))}".strip()

        if self._descrever_imagem is None:
            return texto

        anexo = self._ultimo_anexo_imagem(issue)
        if anexo is None:
            return texto

        chave_cache = f"{chave}:{anexo['id']}"
        descricao_imagem = self._persistencia.obter_analise_imagem(chave_cache)
        if descricao_imagem is None:
            imagem_bytes = self._baixar_anexo(anexo["content"])
            if imagem_bytes is None:
                return texto
            try:
                descricao_imagem = self._descrever_imagem(imagem_bytes)
            except Exception:
                return texto
            self._persistencia.salvar_analise_imagem(chave_cache, descricao_imagem)

        return f"{texto} {descricao_imagem}".strip()

    def _extrair_campos_detalhe(self, campos: dict) -> dict:
        """Campos "de vitrine" pro painel de detalhes (2026-08-15) - nenhum
        deles influencia novidade/pontuação, só exibição. `.get(..., {})` em
        cada custom field porque um ticket pode simplesmente não ter aquele
        campo preenchido (JSM não obriga)."""
        tipo_solicitacao_obj = campos.get(CAMPO_TIPO_SOLICITACAO) or {}
        return {
            "relator": (campos.get("reporter") or {}).get("displayName", ""),
            "responsavel": (campos.get("assignee") or {}).get("displayName", ""),
            "empresa": (campos.get(CAMPO_EMPRESA) or {}).get("value", ""),
            "plataforma": (campos.get(CAMPO_PLATAFORMA) or {}).get("value", ""),
            "tipo_solicitacao": (tipo_solicitacao_obj.get("requestType") or {}).get("name", ""),
        }

    def _extrair_campos_detalhe_com_origem(self, campos: dict, origem: dict | None) -> dict:
        """Perfil N2: Empresa/Plataforma/Tipo de solicitação só existem no NSD
        (campos do Service Desk) - completa o que o ticket de dev não tem, e
        acrescenta o chamado de origem e o N1 (responsável do NSD, quem fala
        com o cliente - vem do Jira, nunca de um nome fixo no código)."""
        detalhe = self._extrair_campos_detalhe(campos)
        if origem is None:
            return detalhe
        detalhe_origem = self._extrair_campos_detalhe(origem["fields"])
        for campo in ("empresa", "plataforma", "tipo_solicitacao"):
            detalhe[campo] = detalhe[campo] or detalhe_origem[campo]
        detalhe["chamado_origem"] = origem["key"]
        detalhe["chamado_origem_url"] = f"{self._base_url}/browse/{origem['key']}"
        detalhe["n1_responsavel"] = detalhe_origem["responsavel"]
        return detalhe

    def _estado_atual(self, issue: dict) -> dict:
        campos = issue["fields"]
        comentarios = campos.get("comment", {}).get("comments", [])
        ultimo = comentarios[-1] if comentarios else None
        return {
            # 🔥 Chave do issue REALMENTE usado pra novidade (2026-08-21) - pro
            # vínculo de 2 saltos ("Aguardando desenvolvimento"), é a chave do
            # ticket VINCULADO (dev), não a do ticket NSD original (ver
            # `_resolver_issue_para_novidade`) - o `status` abaixo já é dele,
            # então o changelog de "quem mudou o status" (`_classificar_evento`)
            # precisa ser consultado no MESMO issue, não no NSD.
            "chave": issue["key"],
            "status": campos["status"]["name"],
            "prioridade": (campos.get("priority") or {}).get("name"),
            "assignee_id": (campos.get("assignee") or {}).get("accountId"),
            "ultimo_comentario_id": ultimo["id"] if ultimo else None,
            "ultimo_comentario_autor_id": ultimo["author"]["accountId"] if ultimo else None,
            "ultimo_comentario_autor_nome": ultimo["author"].get("displayName", "") if ultimo else None,
        }

    def _classificar_evento(self, visto: dict | None, atual: dict) -> tuple:
        """Devolve (novo: bool, tipo: str | None) - o tipo classifica o
        motivo mais relevante da novidade (usado pela fala da GAIA por voz,
        que menciona código+status+urgência, nunca o resumo do ticket - ver
        docs/ARQUITETURA.md). Ordem de checagem = ordem de importância: ticket
        nunca visto > virou crítico > mudou de status > mudou de prioridade
        (não-crítica) > reatribuído > comentário de terceiro.

        🔥 Status mudado pelo PRÓPRIO usuário não conta como novidade
        (2026-08-21, pedido do usuário: "quando a mudança for apenas de
        status realizada por mim, não precisa notificar como novo, apenas
        atualizar o ticket para a coluna nova") - o ticket ainda aparece na
        coluna/categoria certa (isso vem de `atual["status"]`, sempre o
        estado real do Jira, independente de novidade), só não dispara aviso
        de voz nem o badge "NOVO" na lista. Só checa o autor quando o status
        realmente mudou (`_autor_ultima_mudanca_status` custa 1 chamada de
        rede) - continua descendo pras outras checagens (prioridade,
        reatribuição, comentário) porque a MESMA atualização pode ter trazido
        mais de um evento junto."""
        if visto is None:
            return True, "novo"
        prioridade_mudou = visto.get("prioridade") != atual["prioridade"]
        if prioridade_mudou and atual["prioridade"] in PRIORIDADES_CRITICAS:
            return True, "critico"
        status_mudou = visto.get("status") != atual["status"]
        if status_mudou and self._autor_ultima_mudanca_status(atual["chave"]) == self._minha_account_id:
            status_mudou = False
        if status_mudou:
            return True, "status_mudou"
        if prioridade_mudou:
            return True, "prioridade_mudou"
        if visto.get("assignee_id") != atual["assignee_id"]:
            return True, "atribuido"
        if self._comentario_novo_de_terceiro(visto, atual):
            return True, "comentario"
        if self._comentario_novo_de_terceiro(visto, atual, prefixo="origem_"):
            return True, "comentario"
        return False, None

    def _comentario_novo_de_terceiro(self, visto: dict, atual: dict, prefixo: str = "") -> bool:
        """`prefixo="origem_"` checa o NSD de origem (perfil N2, ver
        `_resolver_estado_novidade`) com a mesma regra do ticket principal:
        comentário próprio ou de automação não conta. Estado sem essas
        chaves (perfil N1) simplesmente nunca conta."""
        id_atual = atual.get(f"{prefixo}ultimo_comentario_id")
        if not id_atual or id_atual == visto.get(f"{prefixo}ultimo_comentario_id"):
            return False
        autor_id = atual.get(f"{prefixo}ultimo_comentario_autor_id")
        autor_nome = atual.get(f"{prefixo}ultimo_comentario_autor_nome") or ""
        return autor_id != self._minha_account_id and not self._eh_autor_automatico(autor_nome)

    def buscar_dados_brutos(self) -> list:
        """Parte cara desta classe (JQL x4 + 1 SLA por ticket + Visão/texto de
        urgência quando aplicável) - SEM comparar contra nenhuma persistência,
        pra permitir classificar o MESMO resultado contra mais de uma
        persistência (ex.: fala da GAIA por voz + estado do widget visual, ver
        `_monitorar_jira_voz_loop` em run.py) sem repetir a ida à rede - 1
        chamada aqui, depois `classificar()` quantas vezes precisar (puro,
        sem rede). Antes (2026-08-15) esse custo de rede dobrava a cada ciclo
        porque duas checagens independentes chamavam `listar_categorias()`
        cada uma com sua própria persistência.

        🔥 Isolamento por categoria/ticket (2026-08-23, reportado pelo
        usuário: "clicando no icone do argus e ele nao esta expandindo p
        mostrar as opcoes") - antes, uma falha de rede/timeout ao processar
        UM ticket (SLA, changelog de status, issue vinculado de 2 saltos) ou
        ao buscar a JQL de UMA categoria derrubava esta função INTEIRA sem
        capturar nada - `ArgusWidget.atualizar()` (ver `core/widget.py`)
        então não tinha dado NENHUM pra mostrar, mesmo quando as outras 3
        categorias tinham buscado tudo certinho um instante antes (log real:
        timeout buscando o issue vinculado de UM ticket "Aguardando
        Desenvolvimento" zerava os chips de TODAS as categorias, ciclo após
        ciclo). Agora cada categoria e cada ticket são isolados num
        `try/except requests.RequestException` - uma falha vira só um log e
        aquela categoria/ticket fica de fora NESTE ciclo (reaparece sozinho
        assim que a rede normalizar), sem derrubar o resto que já tinha
        dado certo."""
        dados = []
        for chave_cat, nome_cat, jql in self._definicao_categorias():
            try:
                issues = self._buscar_issues(jql)
            except requests.RequestException as e:
                print(f'[Argus] Falha ao buscar tickets de "{nome_cat}" (tentando de novo no próximo ciclo): {e}')
                continue
            tickets_brutos = []
            for issue in issues:
                chave_ticket = issue["key"]
                try:
                    campos = issue["fields"]
                    atual, origem = self._resolver_estado_novidade(issue)
                    prioridade = (campos.get("priority") or {}).get("name", "")

                    texto_mascarado = mascarar(self._obter_texto_para_analise(issue, chave_ticket))
                    urgencia_no_texto = detectar_urgencia_no_texto(texto_mascarado)
                    # 🔥 SLA só existe no chamado do Service Desk - ticket de
                    # dev responde 404 no endpoint de SLA (confirmado contra a
                    # instância real, 2026-10-01). No perfil N2 o SLA vem do
                    # NSD de origem; ticket de dev sem origem fica sem SLA.
                    if self._eh_chamado_atendimento(chave_ticket):
                        sla_info = self._obter_sla_info(chave_ticket)
                    else:
                        sla_info = self._obter_sla_info(origem["key"]) if origem else None
                    detalhamento_pontuacao = calcular_detalhamento_pontuacao(
                        prioridade, urgencia_no_texto, sla_info,
                    )

                    tickets_brutos.append({
                        "chave": chave_ticket,
                        "resumo": campos["summary"],
                        "status": campos["status"]["name"],
                        "prioridade": prioridade,
                        "atualizado_em": campos["updated"],
                        "pontuacao_foco": detalhamento_pontuacao.total,
                        "detalhamento_pontuacao": detalhamento_pontuacao,
                        "urgencia_no_texto": urgencia_no_texto,
                        "atual": atual,
                        "detalhe": self._extrair_campos_detalhe_com_origem(campos, origem),
                        "sla_texto": (sla_info or {}).get("restante_texto", ""),
                        "sla_estourado": bool(sla_info and sla_info.get("breached")),
                        "sla_restante_millis": (sla_info or {}).get("restante_millis") if sla_info else None,
                    })
                except requests.RequestException as e:
                    print(f"[Argus] Falha ao processar o chamado {chave_ticket} (ignorado neste ciclo): {e}")
                    continue
            dados.append((chave_cat, nome_cat, tickets_brutos))
        return dados

    def classificar(self, dados_brutos: list, persistencia: Persistencia | None = None) -> list:
        """Parte barata (só compara `dados_brutos` - já buscado - contra uma
        persistência, sem rede nenhuma) - `persistencia=None` usa a do próprio
        provider (mesmo comportamento de sempre); passar uma persistência
        diferente permite reaproveitar a mesma busca pra outro "visto" (ex.:
        estado do widget visual) sem chamar a API de novo."""
        persistencia = persistencia or self._persistencia
        categorias = []
        for chave_cat, nome_cat, tickets_brutos in dados_brutos:
            tickets = []
            for tb in tickets_brutos:
                visto = persistencia.obter_estado_ticket(tb["chave"])
                novo, tipo_evento = self._classificar_evento(visto, tb["atual"])
                tickets.append(Ticket(
                    chave=tb["chave"],
                    resumo=tb["resumo"],
                    status=tb["status"],
                    prioridade=tb["prioridade"],
                    url=f"{self._base_url}/browse/{tb['chave']}",
                    atualizado_em=tb["atualizado_em"],
                    novo=novo,
                    tipo_evento=tipo_evento,
                    pontuacao_foco=tb["pontuacao_foco"],
                    detalhamento_pontuacao=tb.get("detalhamento_pontuacao"),
                    urgencia_no_texto=tb["urgencia_no_texto"],
                    sla_texto=tb["sla_texto"],
                    sla_estourado=tb["sla_estourado"],
                    sla_restante_millis=tb["sla_restante_millis"],
                    **tb["detalhe"],
                ))
            # 🔥 Ordena por pontuação de foco (2026-08-15, pedido do usuário: "pra
            # eu saber qual focar") - maior pontuação primeiro, dentro de cada
            # categoria (a JQL acima só define QUAIS tickets entram, não a ordem
            # de exibição).
            tickets.sort(key=lambda t: t.pontuacao_foco, reverse=True)
            categorias.append(Categoria(
                chave=chave_cat, nome_exibicao=nome_cat, tickets=tickets,
                mostrar_status_na_lista=chave_cat in CHAVES_CATEGORIAS_N2,
            ))
        return categorias

    def listar_categorias(self) -> list:
        return self.classificar(self.buscar_dados_brutos())

    def marcar_visto(self, chave_ticket: str) -> None:
        issue = self._obter_issue_completo(chave_ticket)
        estado, _ = self._resolver_estado_novidade(issue)
        self._persistencia.salvar_estado_ticket(chave_ticket, estado)

    def obter_detalhes_completos(self, chave_ticket: str) -> dict:
        """Busca SOB DEMANDA (só quando o usuário abre o painel de detalhes de
        um ticket, ver core/widget.py) - description + TODOS os comentários,
        diferente da checagem periódica (`buscar_dados_brutos`), que só olha o
        ÚLTIMO comentário pra detectar novidade. Pensado pro botão "Analisar"
        (2026-08-15, pedido do usuário: "hoje eu costumo copiar toda a
        descrição do ticket junto com toda a resposta que um dev me deu, e
        colar no gpt") - dá pro consumidor (ex.: GAIA) montar o mesmo material
        que o usuário já cola manualmente, sem chamada extra de rede."""
        issue = self._obter_issue_completo(chave_ticket)
        campos = issue["fields"]
        descricao = self._texto_plano_adf(campos.get("description"))
        comentarios = self._comentarios_texto(campos)
        # 🔥 Perfil N2 (2026-10-01) - a conversa com o cliente acontece no NSD
        # de origem, não no ticket de dev. Junta a descrição e os comentários
        # dele (marcados com a chave do NSD) pra análise ter o mesmo contexto
        # que o N1 tem.
        vinculo = None if self._eh_chamado_atendimento(chave_ticket) else self._chamado_origem(issue)
        if vinculo is not None:
            campos_origem = self._obter_issue_completo(vinculo["key"])["fields"]
            descricao_origem = self._texto_plano_adf(campos_origem.get("description"))
            descricao = f"{descricao}\n\n[Chamado de origem {vinculo['key']}]\n{descricao_origem}".strip()
            comentarios_origem = [
                {**c, "autor": f"{c['autor']} ({vinculo['key']})"}
                for c in self._comentarios_texto(campos_origem)
            ]
            comentarios = sorted(comentarios + comentarios_origem, key=lambda c: c["criado_em"])
        return {"descricao": descricao, "comentarios": comentarios}

    def _comentarios_texto(self, campos: dict) -> list:
        return [
            {
                "autor": (comentario.get("author") or {}).get("displayName", ""),
                "texto": self._texto_plano_adf(comentario.get("body")),
                "criado_em": comentario.get("created", ""),
            }
            for comentario in campos.get("comment", {}).get("comments", [])
        ]
