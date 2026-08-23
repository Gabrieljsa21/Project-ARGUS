"""Diagnóstico MANUAL (não é um teste automatizado) pra investigar o relato
"o ticket só é selecionado se o mouse estiver em cima do texto" - abre uma
janela DE VERDADE (não offscreen) com 3 linhas de ticket parecidas com as do
print de tela do usuário, e imprime no console toda vez que o hover
liga/desliga em cada linha, junto da posição exata do mouse.

Rodar com CONSOLE visível (não pythonw), a partir da raiz do projeto:

    .venv\\Scripts\\python.exe testes\\diagnostico_hover_linha_ticket.py

Depois é só mover o mouse devagar: sobre o texto do código/resumo de uma
linha, sobre o espaço vazio à direita dela (onde não tem nada escrito), e
entre uma linha e outra. O console mostra exatamente quando cada linha
"liga"/"desliga" o hover (fundo dourado na janela) e a posição do mouse
naquele instante - se "desligar" assim que o mouse sai do texto mas ainda
dentro da linha, o bug ainda existe; se só desligar ao sair da linha
inteira, está correto.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import QPoint
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel

from argus.core.widget import _LinhaTicket
from argus.modelos import Ticket

TICKETS = [
    Ticket("NSD-13311", "Pedido não integrando", "Aguardando cliente", "Highest", "https://example.com/a", "2026-08-14"),
    Ticket("NSD-13274", "Erro ao integrar os pedidos no SAP B1", "Aguardando cliente", "Highest", "https://example.com/b", "2026-08-14"),
    Ticket(
        "NSD-13317",
        "PEDIDO COM ENDERECO ALTERADO NO SITE E DEPOIS NO APP DA NORDWARE - mas continua com erro",
        "Aguardando cliente", "Low", "https://example.com/c", "2026-08-14", novo=True,
    ),
]


class _LinhaTicketComLog(_LinhaTicket):
    """Mesma _LinhaTicket de verdade, só que imprime no console quando o
    hover liga/desliga, pra ver no terminal exatamente o que o código
    interno está enxergando enquanto você move o mouse na janela."""

    def enterEvent(self, evento):
        super().enterEvent(evento)
        print(f"[{self._ticket.chave}] hover LIGOU  - mouse local em {self.mapFromGlobal(evento.globalPos()).toTuple() if hasattr(evento, 'globalPos') else '?'}")

    def leaveEvent(self, evento):
        super().leaveEvent(evento)
        print(f"[{self._ticket.chave}] hover DESLIGOU")

    def mousePressEvent(self, evento):
        print(f"[{self._ticket.chave}] CLIQUE em {evento.position().toPoint().toTuple()}")
        super().mousePressEvent(evento)


def main():
    app = QApplication(sys.argv)

    janela = QWidget()
    janela.setWindowTitle("Diagnóstico hover - Argus")
    janela.setStyleSheet("background-color: #14141c;")
    janela.resize(650, 220)

    layout = QVBoxLayout(janela)
    layout.setContentsMargins(14, 10, 14, 12)
    layout.setSpacing(8)

    aviso = QLabel(
        "Mova o mouse sobre o TEXTO e depois sobre o ESPAÇO VAZIO de cada linha.\n"
        "Observe o console (deve imprimir LIGOU/DESLIGOU) e o fundo dourado da janela."
    )
    aviso.setStyleSheet("color: #aaaaaa; background: transparent;")
    layout.addWidget(aviso)

    fonte = QFont("Segoe UI", 11)
    largura_disponivel = 620
    for ticket in TICKETS:
        from PySide6.QtGui import QFontMetrics
        sufixo = " ● NOVO" if ticket.novo else ""
        prefixo_plano = f"[{ticket.pontuacao_foco}] {ticket.chave}  "
        metricas = QFontMetrics(fonte)
        largura_resumo = max(0, largura_disponivel - 30 - metricas.horizontalAdvance(prefixo_plano))
        from PySide6.QtCore import Qt as _Qt
        resumo_elidido = metricas.elidedText(f"— {ticket.resumo}{sufixo}", _Qt.ElideRight, largura_resumo)
        linha = _LinhaTicketComLog(ticket, resumo_elidido, fonte, lambda t: None)
        layout.addWidget(linha)

    janela.show()
    print("Janela aberta - mova o mouse sobre as linhas e observe este console.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
