"""Validação manual - sobe a janela com um provider FALSO (sem tocar no Jira de
verdade) pra confirmar que a UI instancia, reconstroi a barra e alterna
novidades/total sem quebrar. Rodar com QT_QPA_PLATFORM=offscreen (sem
precisar de display real) a partir da raiz do projeto:

    QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe testes/testar_widget_com_provider_falso.py
"""

import sys
import tempfile
import os

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from argus.core.widget import ArgusWidget
from argus.modelos import Categoria, Ticket
from argus.persistencia import PersistenciaArquivo
from argus.providers.base import NotificacaoProvider


class ProviderFalso(NotificacaoProvider):
    def listar_categorias(self):
        return [
            Categoria("em_revisao", "Em Revisão", []),
            Categoria("atendimento", "Aguardando Atendimento", [
                Ticket("NSD-1", "Erro X", "Aguardando atendimento", "High", "https://example.com/NSD-1", "2026-08-14", novo=True),
                Ticket("NSD-2", "Erro Y", "Aguardando atendimento", "Low", "https://example.com/NSD-2", "2026-08-14", novo=False),
            ]),
            Categoria("cliente", "Aguardando Cliente", []),
            Categoria("dev", "Aguardando Desenvolvimento", [
                Ticket("NSD-3", "Falha Z", "Aguardando desenvolvimento", "High", "https://example.com/NSD-3", "2026-08-14", novo=True),
            ]),
        ]

    def marcar_visto(self, chave_ticket):
        print(f"marcar_visto({chave_ticket})")


def main():
    caminho_config = os.path.join(tempfile.gettempdir(), "argus_teste_config.json")
    app = QApplication(sys.argv)
    widget = ArgusWidget(ProviderFalso(), PersistenciaArquivo(caminho_config))
    widget.show()
    print("OK: categorias:", [(c.chave, c.novidades, c.total) for c in widget._categorias])
    print("OK: botoes (novidades):", [b.text() for b in widget._botoes_categoria])
    widget._alternar_modo()
    print("OK: botoes (total):", [b.text() for b in widget._botoes_categoria])


if __name__ == "__main__":
    main()
