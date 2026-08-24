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

    # 🔥 Menu de Configurações (2026-08-16, ver
    # argus/core/widget.py::_DialogoConfiguracoes) - também NÃO é
    # @abstractmethod, mesmo motivo acima. Um dicionário genérico (em vez de
    # um par obter/salvar por opção) pra não precisar estender a interface de
    # novo a cada configuração nova que o menu ganhar no futuro.
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
    la") - antes, `__init__` carregava o arquivo 1x pra `self._dado` e todo
    getter lia dali, nunca do disco de novo. A GAIA mantém sua PRÓPRIA
    instância de longa duração (`run.py::_obter_persistencia_estado_widget`,
    singleton "lazy", 1x por processo) SEPARADA da instância que o widget usa
    (`ui/qt_painel.py::_abrir_argus_widget`, criada só quando o usuário abre o
    Argus) - as duas apontam pro MESMO arquivo, mas cada uma tinha sua própria
    cópia em memória. Quando o usuário via um ticket no widget, só a cópia DO
    WIDGET era atualizada (memória + disco); a cópia da GAIA continuava com o
    snapshot antigo pra sempre (nunca recarregava do disco), então o lembrete
    de voz continuava achando o ticket "não visto" indefinidamente, mesmo já
    visto no widget. Cada getter agora lê do disco na hora - arquivo pequeno,
    custo desprezível, e elimina essa classe inteira de bug (mesmo raciocínio
    já aplicado a outras variáveis "lidas 1x, nunca atualizadas" no ecossistema
    GAIA)."""

    def __init__(self, caminho: str | None = None):
        self.caminho = caminho or os.path.join(os.path.expanduser("~"), ".argus", "config.json")
        pasta = os.path.dirname(self.caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)

    def _carregar(self) -> dict:
        if os.path.exists(self.caminho):
            try:
                with open(self.caminho, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _salvar(self, dado: dict) -> None:
        with open(self.caminho, "w", encoding="utf-8") as f:
            json.dump(dado, f, indent=2, ensure_ascii=False)

    def obter_estado_ticket(self, chave: str) -> dict | None:
        return self._carregar().get("tickets", {}).get(chave)

    def salvar_estado_ticket(self, chave: str, estado: dict) -> None:
        dado = self._carregar()
        dado.setdefault("tickets", {})[chave] = estado
        self._salvar(dado)

    def obter_posicao_janela(self) -> tuple | None:
        posicao = self._carregar().get("posicao_janela")
        return tuple(posicao) if posicao else None

    def salvar_posicao_janela(self, x: int, y: int) -> None:
        dado = self._carregar()
        dado["posicao_janela"] = [x, y]
        self._salvar(dado)

    def obter_analise_imagem(self, chave: str) -> str | None:
        return self._carregar().get("analises_imagem", {}).get(chave)

    def salvar_analise_imagem(self, chave: str, texto: str) -> None:
        dado = self._carregar()
        dado.setdefault("analises_imagem", {})[chave] = texto
        self._salvar(dado)

    def obter_configuracoes(self) -> dict:
        return self._carregar().get("configuracoes", {})

    def salvar_configuracoes(self, configuracoes: dict) -> None:
        dado = self._carregar()
        dado["configuracoes"] = configuracoes
        self._salvar(dado)
