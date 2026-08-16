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
    # 🔥 Pontuação de foco 1-100 (2026-08-15, pedido do usuário: "gerar uma fila
    # de tickets ordenados por prioridade q ele definiu, com valores de 1 a 100
    # para cada ticket... pra eu saber qual focar") - SÓ pra ordenar/exibir no
    # Argus, nunca escreve nada de volta no Jira (ver argus/pontuacao.py). 50 é
    # o valor neutro (prioridade "Medium") usado quando ainda não foi calculado.
    pontuacao_foco: int = 50
    urgencia_no_texto: bool = False
    # 🔥 Detalhe pro painel de detalhes (2026-08-15, pedido do usuário: "abra
    # um modal a direita, com as informações mais detalhadas do ticket") - só
    # os campos rápidos de listar (já vêm na busca periódica); descrição +
    # TODOS os comentários são sob demanda, ver JiraProvider.obter_detalhes_completos.
    relator: str = ""
    responsavel: str = ""
    empresa: str = ""
    plataforma: str = ""
    tipo_solicitacao: str = ""
    sla_texto: str = ""
    sla_estourado: bool = False


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
