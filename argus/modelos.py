"""Estruturas de dado que atravessam a fronteira provider -> core. O core/ (janela,
barra, listas) só enxerga Ticket/Categoria - nunca um dict cru de resposta de API."""

from dataclasses import dataclass, field


@dataclass
class Ticket:
    chave: str
    resumo: str
    status: str
    prioridade: str
    url: str
    atualizado_em: str
    novo: bool = False
    # 🔥 Tipo do evento que tornou o ticket "novo" (2026-08-15, pra fala da
    # GAIA por voz - ver ARQUITETURA.md) - "novo"/"critico"/"status_mudou"/
    # "prioridade_mudou"/"atribuido"/"comentario", ou None se `novo=False`.
    # O core/ (janela) não usa isso pra nada hoje - só existe pra quem
    # consome o provider precisar de mais contexto que um bool.
    tipo_evento: str = None


@dataclass
class Categoria:
    chave: str
    nome_exibicao: str
    tickets: list = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.tickets)

    @property
    def novidades(self) -> int:
        return sum(1 for t in self.tickets if t.novo)
