"""Onde o Argus guarda o que já foi visto (por ticket) e a posição da janela.
Abstrato de propósito - PersistenciaArquivo (abaixo) é o uso standalone (arquivo
JSON próprio); rodando dentro da GAIA, ela passa uma implementação que grava no
brain.json dela em vez de criar um arquivo à parte. O core/ e os providers só
conhecem a interface `Persistencia`, nunca uma das duas implementações."""

from abc import ABC, abstractmethod
import json
import os


class Persistencia(ABC):
    @abstractmethod
    def obter_estado_ticket(self, chave: str) -> dict | None:
        """Última "foto" do ticket (status/prioridade/assignee/último comentário)
        no momento em que o usuário abriu ele pela última vez - None se nunca
        visto. Usado pelo provider pra decidir se há novidade (ver JiraProvider.
        _eh_novidade)."""
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


class PersistenciaArquivo(Persistencia):
    """Uso standalone - um arquivo JSON próprio (padrão: ~/.argus/config.json),
    nada a ver com a GAIA."""

    def __init__(self, caminho: str | None = None):
        self.caminho = caminho or os.path.join(os.path.expanduser("~"), ".argus", "config.json")
        pasta = os.path.dirname(self.caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        self._dado = self._carregar()

    def _carregar(self) -> dict:
        if os.path.exists(self.caminho):
            try:
                with open(self.caminho, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _salvar(self) -> None:
        with open(self.caminho, "w", encoding="utf-8") as f:
            json.dump(self._dado, f, indent=2, ensure_ascii=False)

    def obter_estado_ticket(self, chave: str) -> dict | None:
        return self._dado.get("tickets", {}).get(chave)

    def salvar_estado_ticket(self, chave: str, estado: dict) -> None:
        self._dado.setdefault("tickets", {})[chave] = estado
        self._salvar()

    def obter_posicao_janela(self) -> tuple | None:
        posicao = self._dado.get("posicao_janela")
        return tuple(posicao) if posicao else None

    def salvar_posicao_janela(self, x: int, y: int) -> None:
        self._dado["posicao_janela"] = [x, y]
        self._salvar()

    def obter_analise_imagem(self, chave: str) -> str | None:
        return self._dado.get("analises_imagem", {}).get(chave)

    def salvar_analise_imagem(self, chave: str, texto: str) -> None:
        self._dado.setdefault("analises_imagem", {})[chave] = texto
        self._salvar()
