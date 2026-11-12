"""Onde o Argus guarda o que já foi visto (por ticket) e a posição da janela.
Abstrato de propósito - PersistenciaArquivo (abaixo) é o uso standalone (arquivo
JSON próprio); rodando dentro da GAIA, ela passa uma implementação que grava no
brain.json dela em vez de criar um arquivo à parte. O core/ e os providers só
conhecem a interface `Persistencia`, nunca uma das duas implementações."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import json
import os
import threading
import time

# Estado de ticket sem gravação há mais que isso é podado ao abrir (ticket
# concluído há muito tempo). Se um dia ele voltar à fila, só aparece como novo.
DIAS_RETENCAO_ESTADO_TICKET = 180
CAMPO_SALVO_EM = "_salvo_em"
TENTATIVAS_TROCA_ARQUIVO = 5


class Persistencia(ABC):
    @abstractmethod
    def obter_estado_ticket(self, chave: str) -> dict | None:
        """Última "foto" do ticket (status/prioridade/assignee/último comentário)
        no momento em que o usuário abriu ele pela última vez - None se nunca
        visto. Usado pelo provider pra decidir se há novidade (ver JiraProvider.
        _classificar_evento)."""
        raise NotImplementedError

    @abstractmethod
    def salvar_estado_ticket(self, chave: str, estado: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def obter_posicao_janela(self) -> tuple | None:
        raise NotImplementedError

    @abstractmethod
    def salvar_posicao_janela(self, x: int, y: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def obter_analise_imagem(self, chave: str) -> str | None:
        """Descrição (via visão) já extraída de um print de tela anexado ao
        ticket - cacheada pra não chamar o modelo de visão de novo a cada
        polling pro MESMO anexo (ver JiraProvider._obter_texto_para_analise)."""
        raise NotImplementedError

    @abstractmethod
    def salvar_analise_imagem(self, chave: str, texto: str) -> None:
        raise NotImplementedError

    # 🔥 Menu de Configurações (2026-08-16, ver
    # argus/core/widget.py::_DialogoConfiguracoes) - NÃO é @abstractmethod,
    # pra não quebrar implementações de fora (a da GAIA). Um dicionário
    # genérico (em vez de um par obter/salvar por opção) pra não precisar
    # estender a interface de novo a cada configuração nova do menu.
    def obter_configuracoes(self) -> dict:
        """Configurações ajustáveis pelo menu (ex.: `limite_janelas_destacadas`,
        `chacoalhada_ativa`) - dict vazio se nunca foi salvo (cada consumidor
        aplica seu próprio padrão via `dict.get`)."""
        return {}

    def salvar_configuracoes(self, configuracoes: dict) -> None:
        pass


class PersistenciaArquivo(Persistencia):
    """Uso standalone - um arquivo JSON próprio (padrão: ~/.argus/config.json),
    nada a ver com a GAIA.

    🔥 SEM cache em memória de propósito (2026-08-24, bug real: "a gaia esta
    falando q tem ticket pendente pra visualizar no argus mas n tem nada novo
    la") - a GAIA e o widget mantêm instâncias SEPARADAS apontando pro MESMO
    arquivo; com cópia em memória, a da GAIA nunca via o que o widget marcava
    como visto. Cada getter lê do disco na hora (arquivo pequeno, custo
    desprezível).

    🔥 Gravação atômica e sob trava (2026-11-12): antes, cada `salvar_*`
    escrevia direto no arquivo. Um leitor que pegasse o JSON pela metade
    recebia `{}` e a gravação seguinte apagava todos os "vistos" (tudo voltava
    a ser NOVO). Agora escreve num temporário e troca de uma vez
    (`os.replace`), e o ler-alterar-gravar fica sob uma trava (a GAIA grava do
    loop de voz e o widget, das threads de busca/visto, no mesmo processo)."""

    def __init__(self, caminho: str | None = None, dias_retencao: int = DIAS_RETENCAO_ESTADO_TICKET):
        self.caminho = caminho or os.path.join(os.path.expanduser("~"), ".argus", "config.json")
        pasta = os.path.dirname(self.caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        self._trava = threading.RLock()
        self.podar(dias_retencao)

    def _carregar(self) -> dict:
        if not os.path.exists(self.caminho):
            return {}
        try:
            with open(self.caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            # Arquivo ilegível: guarda à parte pra recuperação manual, em vez
            # de deixar a próxima gravação sobrescrever com um estado vazio.
            destino = f"{self.caminho}.corrompido-{datetime.now():%Y%m%d-%H%M%S}"
            try:
                os.replace(self.caminho, destino)
                print(f"[Argus] Estado ilegível guardado em {destino}; começando do zero.")
            except OSError:
                pass
            return {}

    def _salvar(self, dado: dict) -> None:
        """No Windows a troca falha se outro processo estiver lendo o arquivo
        naquele instante (ex.: o Argus standalone e a GAIA ao mesmo tempo) -
        tenta de novo algumas vezes antes de desistir."""
        temporario = f"{self.caminho}.tmp"
        with open(temporario, "w", encoding="utf-8") as f:
            json.dump(dado, f, indent=2, ensure_ascii=False)
        for tentativa in range(TENTATIVAS_TROCA_ARQUIVO):
            try:
                os.replace(temporario, self.caminho)
                return
            except PermissionError:
                if tentativa == TENTATIVAS_TROCA_ARQUIVO - 1:
                    raise
                time.sleep(0.05)

    def _alterar(self, alteracao) -> None:
        with self._trava:
            dado = self._carregar()
            alteracao(dado)
            self._salvar(dado)

    def podar(self, dias_retencao: int = DIAS_RETENCAO_ESTADO_TICKET) -> int:
        """Remove estados de ticket sem gravação há mais de `dias_retencao`
        dias e as análises de imagem de tickets que não têm mais estado. Estado
        gravado antes deste campo existir ganha a data de hoje (começa a contar
        agora). Devolve quantos tickets saíram."""
        agora = datetime.now()
        limite = (agora - timedelta(days=dias_retencao)).isoformat(timespec="seconds")
        with self._trava:
            dado = self._carregar()
            tickets = dado.get("tickets", {})
            mudou = False
            removidos = 0
            for chave, estado in list(tickets.items()):
                salvo_em = (estado or {}).get(CAMPO_SALVO_EM)
                if salvo_em is None:
                    tickets[chave] = {**(estado or {}), CAMPO_SALVO_EM: agora.isoformat(timespec="seconds")}
                    mudou = True
                elif salvo_em < limite:
                    del tickets[chave]
                    removidos += 1
                    mudou = True
            analises = dado.get("analises_imagem", {})
            for chave_cache in list(analises):
                if chave_cache.split(":", 1)[0] not in tickets:
                    del analises[chave_cache]
                    mudou = True
            if mudou:
                self._salvar(dado)
        return removidos

    def obter_estado_ticket(self, chave: str) -> dict | None:
        return self._carregar().get("tickets", {}).get(chave)

    def salvar_estado_ticket(self, chave: str, estado: dict) -> None:
        estado = {**estado, CAMPO_SALVO_EM: datetime.now().isoformat(timespec="seconds")}
        self._alterar(lambda dado: dado.setdefault("tickets", {}).__setitem__(chave, estado))

    def obter_posicao_janela(self) -> tuple | None:
        posicao = self._carregar().get("posicao_janela")
        return tuple(posicao) if posicao else None

    def salvar_posicao_janela(self, x: int, y: int) -> None:
        self._alterar(lambda dado: dado.__setitem__("posicao_janela", [x, y]))

    def obter_analise_imagem(self, chave: str) -> str | None:
        return self._carregar().get("analises_imagem", {}).get(chave)

    def salvar_analise_imagem(self, chave: str, texto: str) -> None:
        self._alterar(lambda dado: dado.setdefault("analises_imagem", {}).__setitem__(chave, texto))

    def obter_configuracoes(self) -> dict:
        return self._carregar().get("configuracoes", {})

    def salvar_configuracoes(self, configuracoes: dict) -> None:
        self._alterar(lambda dado: dado.__setitem__("configuracoes", configuracoes))
