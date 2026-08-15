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

from argus.core.tema import aplicar_estilo_global
from argus.core.widget import ArgusWidget
from argus.modelos import Categoria, Ticket
from argus.persistencia import PersistenciaArquivo
from argus.providers.base import NotificacaoProvider


class ProviderFalso(NotificacaoProvider):
    def listar_categorias(self):
        return [
            Categoria("em_revisao", "Em Revisão", []),
            Categoria("atendimento", "Aguardando Atendimento", [
                Ticket(f"NSD-{i}", f"Erro {i}", "Aguardando atendimento", "High", f"https://example.com/NSD-{i}", "2026-08-14", novo=True)
                for i in range(1, 8)  # 7 tickets - forca o caminho com QScrollArea (MAX_LINHAS_VISIVEIS = 5)
            ]),
            Categoria("cliente", "Aguardando Cliente", []),
            Categoria("dev", "Aguardando Desenvolvimento", [
                Ticket("NSD-99", "Falha Z", "Aguardando desenvolvimento", "High", "https://example.com/NSD-99", "2026-08-14", novo=True),
            ]),
        ]

    def marcar_visto(self, chave_ticket):
        print(f"marcar_visto({chave_ticket})")


def main():
    caminho_config = os.path.join(tempfile.gettempdir(), "argus_teste_config.json")
    app = QApplication(sys.argv)
    widget = ArgusWidget(ProviderFalso(), PersistenciaArquivo(caminho_config))
    widget.show()
    app.processEvents()  # esvazia o singleShot(0) agendado por atualizar() no __init__ antes de continuar
    print("OK: categorias:", [(c.chave, c.novidades, c.total) for c in widget._categorias])
    print("OK: chips (novidades):", [(c.categoria.chave) for c in widget._chips])

    widget._hover_entrou_categoria(widget._categorias[1])
    print("OK: painel visivel apos hover:", widget._painel.isVisible())
    print("OK: chave aberta:", widget._chave_categoria_aberta)

    widget._categoria_clicada(widget._categorias[1])
    print("OK: fixado apos clique:", widget._fixado)
    widget._fechar_painel_se_nao_fixado()
    print("OK: painel continua visivel mesmo com timeout (fixado):", widget._painel.isVisible())

    widget._categoria_clicada(widget._categorias[1])  # desfixa de novo
    widget._fechar_painel_se_nao_fixado()
    print("OK: painel fecha com timeout apos desfixar:", not widget._painel.isVisible())

    widget._alternar_modo()
    print("OK: chips (total):", [(c.categoria.chave) for c in widget._chips])

    # categoria GRANDE (atendimento, 7 tickets) -> categoria PEQUENA (dev, 1 ticket)
    # - reproduz o bug relatado: "acontece quando uma janela com varios itens
    # esta aberta e eu vou para uma com poucos".
    widget._hover_entrou_categoria(widget._categorias[1])  # atendimento, 7 tickets
    app.processEvents()
    altura_grande = widget.height()
    print("OK: altura com categoria grande (7 tickets):", altura_grande)

    widget._hover_entrou_categoria(widget._categorias[3])  # dev, 1 ticket
    app.processEvents()
    altura_pequena = widget.height()
    print("OK: altura com categoria pequena (1 ticket):", altura_pequena)
    print("OK: encolheu de verdade:", altura_pequena < altura_grande)


if __name__ == "__main__":
    main()
