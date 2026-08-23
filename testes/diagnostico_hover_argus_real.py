"""Diagnóstico MANUAL v2 - diferente de diagnostico_hover_linha_ticket.py
(que usava uma janela NORMAL/opaca e o hover se mostrou correto), este aqui
sobe o `ArgusWidget` DE VERDADE (mesmas flags de janela: sem borda, sempre no
topo, fundo translúcido) com dados falsos (sem precisar de rede/credencial),
pra testar se o comportamento muda quando a janela é a flutuante real - é
exatamente esse tipo de janela (Qt.Tool | FramelessWindowHint |
WindowStaysOnTopHint + WA_TranslucentBackground) que pode se comportar
diferente de uma QWidget comum no Windows.

Rodar com CONSOLE visível, a partir da raiz do projeto:

    .venv\\Scripts\\python.exe testes\\diagnostico_hover_argus_real.py

Clique na coruja/ícone (ou espere - a categoria "Aguardando Cliente" já
some fixada) e mova o mouse sobre as linhas de ticket: texto e espaço vazio.
"""
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QApplication

import argus.core.widget as widget_mod
from argus.core.widget import ArgusWidget, _LinhaTicket
from argus.modelos import Categoria, Ticket
from argus.persistencia import PersistenciaArquivo
from argus.providers.base import NotificacaoProvider

_original_enter = _LinhaTicket.enterEvent
_original_leave = _LinhaTicket.leaveEvent
_original_press = _LinhaTicket.mousePressEvent


def _enter_com_log(self, evento):
    _original_enter(self, evento)
    print(f"[{self._ticket.chave}] hover LIGOU")


def _leave_com_log(self, evento):
    _original_leave(self, evento)
    print(f"[{self._ticket.chave}] hover DESLIGOU")


def _press_com_log(self, evento):
    print(f"[{self._ticket.chave}] CLIQUE")
    _original_press(self, evento)


widget_mod._LinhaTicket.enterEvent = _enter_com_log
widget_mod._LinhaTicket.leaveEvent = _leave_com_log
widget_mod._LinhaTicket.mousePressEvent = _press_com_log


def _tickets_genericos(prefixo, quantidade, status):
    return [
        Ticket(f"{prefixo}-{100 + i}", f"Ticket genérico {i}", status, "Medium", f"https://example.com/{prefixo}{i}", "2026-08-14")
        for i in range(quantidade)
    ]


class ProviderFalso(NotificacaoProvider):
    def listar_categorias(self):
        # 🔥 Contagens iguais ao print real do usuário (1/4/3/6) - categoria
        # vazia SOME da barra (ver `_reconstruir_barra`), o que deixava a
        # barra/painel bem mais ESTREITOS que o uso real e o texto acabava
        # ocupando a largura inteira, sem sobrar vão vazio pra testar.
        return [
            Categoria("em_revisao", "Em Revisão", _tickets_genericos("REV", 1, "Em Revisão")),
            Categoria("atendimento", "Aguardando Atendimento", _tickets_genericos("ATD", 4, "Aguardando atendimento")),
            Categoria("cliente", "Aguardando Cliente", [
                Ticket("NSD-13311", "Pedido não integrando", "Aguardando cliente", "Highest", "https://example.com/a", "2026-08-14"),
                Ticket("NSD-13274", "Erro ao integrar os pedidos no SAP B1", "Aguardando cliente", "Highest", "https://example.com/b", "2026-08-14"),
                Ticket(
                    "NSD-13317",
                    "PEDIDO COM ENDERECO ALTERADO NO SITE E DEPOIS NO APP DA NORDWARE - mas continua com erro",
                    "Aguardando cliente", "Low", "https://example.com/c", "2026-08-14", novo=True,
                ),
            ]),
            Categoria("dev", "Aguardando Desenvolvimento", _tickets_genericos("DEV", 6, "Aguardando desenvolvimento")),
        ]

    def marcar_visto(self, chave_ticket):
        pass


def main():
    app = QApplication(sys.argv)

    caminho_config = os.path.join(tempfile.gettempdir(), "argus_diagnostico_hover_real.json")
    if os.path.exists(caminho_config):
        os.remove(caminho_config)

    widget = ArgusWidget(ProviderFalso(), PersistenciaArquivo(caminho_config))
    widget.move(200, 200)
    widget.show()

    def _abrir_categoria():
        # 🔥 modo TOTAL (2026-08-23) - os tickets genéricos não são "novo",
        # então no modo padrão (novidades) as categorias sem nenhum ticket
        # novo somem da barra (ver `_reconstruir_barra`) - a barra ficava
        # estreita de novo (só 1 chip), mesmo com os tickets cadastrados.
        # Modo total mostra TODAS as categorias com total > 0, igual ao
        # print real do usuário (1/4/3/6).
        widget._modo_total = True
        widget._reconstruir_barra()
        cat = next((c for c in widget._categorias if c.chave == "cliente"), None)
        if cat:
            widget._categoria_clicada(cat)
            print("Categoria 'Aguardando Cliente' aberta e fixada - mova o mouse sobre as linhas.")

    from PySide6.QtCore import QTimer
    QTimer.singleShot(500, _abrir_categoria)

    print("Janela real do Argus aberta (fundo translucido, sem borda, sempre no topo).")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
