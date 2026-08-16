"""Contrato entre o core/ (janela, barra, listas) e qualquer fonte de dado. O
core/ nunca sabe se por trás tem Jira ou outra coisa - só fala com isto."""

from abc import ABC, abstractmethod


class NotificacaoProvider(ABC):
    @abstractmethod
    def listar_categorias(self) -> list:
        """Devolve list[Categoria] com os tickets atuais, já com `novo` calculado
        (ver Persistencia) - uma chamada por atualização periódica."""
        raise NotImplementedError

    @abstractmethod
    def marcar_visto(self, chave_ticket: str) -> None:
        """Registra que o usuário abriu este ticket agora - a próxima chamada de
        listar_categorias() não vai mais marcar `novo` pra ele, a menos que algo
        mude de novo depois disso."""
        raise NotImplementedError
