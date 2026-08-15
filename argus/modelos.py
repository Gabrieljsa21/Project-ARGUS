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
