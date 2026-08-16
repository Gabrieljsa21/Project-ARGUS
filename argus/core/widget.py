"""Janela principal do Argus - sempre no topo, transparente, sem borda,
arrastável (ver ARQUITETURA.md, seção "Janela"). Não sabe o que é Jira - só
fala com `NotificacaoProvider`/`Persistencia`.

A personagem/animação é OPCIONAL e decorativa (ver ARQUITETURA.md) - esta
versão ainda não tem nenhuma arte, só um círculo pequeno (`_Alavanca`) no lugar
dela, que já implementa a mecânica real (clique alterna novidades/total,
arrastar move a janela) - trocar por uma personagem animada depois não muda
essa mecânica, só o desenho.

Simplificação deliberada de MVP: sem máscara de alpha por pixel (que só faz
sentido quando existe uma silhueta de personagem irregular) - o clique-através
aqui vem de mascarar a janela pro formato de retângulo arredondado que ela
mesma desenha, então não sobra nenhuma margem transparente clicável."""

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPainterPath, QColor, QRegion
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QDialog, QLabel, QScrollArea,
)

LIMIAR_ARRASTAR_PIXELS = 6
COR_FUNDO = QColor(20, 20, 25, 200)
RAIO_CANTO = 14


class _Alavanca(QWidget):
    """Placeholder do lugar da personagem - widget PRÓPRIO (não QPushButton
    comum) porque precisa diferenciar clique de arrastar no mesmo gesto de
    mouse, o que um botão padrão do Qt não faz sozinho (um QPushButton some o
    evento de clique se o mouse se mover pra fora dele antes de soltar, não dá
    pra usar isso pra mover a janela ao mesmo tempo)."""

    def __init__(self, ao_clicar, parent=None):
        super().__init__(parent)
        self._ao_clicar = ao_clicar
        self._pos_pressionada = None
        self._arrastou = False
        self.setFixedSize(26, 26)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        pintor.setBrush(QColor(90, 130, 255))
        pintor.setPen(Qt.NoPen)
        pintor.drawEllipse(1, 1, 24, 24)

    def mousePressEvent(self, evento):
        self._pos_pressionada = evento.globalPosition().toPoint()
        self._arrastou = False

    def mouseMoveEvent(self, evento):
        if self._pos_pressionada is None:
            return
        atual = evento.globalPosition().toPoint()
        delta = atual - self._pos_pressionada
        if delta.manhattanLength() > LIMIAR_ARRASTAR_PIXELS:
            self._arrastou = True
            janela = self.window()
            janela.move(janela.pos() + (atual - self._pos_pressionada))
            self._pos_pressionada = atual

    def mouseReleaseEvent(self, evento):
        if not self._arrastou:
            self._ao_clicar()
        self._pos_pressionada = None


class ArgusWidget(QWidget):
    def __init__(self, provider, persistencia):
        super().__init__()
        self._provider = provider
        self._persistencia = persistencia
        self._modo_total = False
        self._categorias = []
        self._botoes_categoria = []
        self._pos_pressionada = None

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(6)
        self._alavanca = _Alavanca(self._alternar_modo, self)
        self._layout.addWidget(self._alavanca)

        posicao_salva = self._persistencia.obter_posicao_janela()
        if posicao_salva:
            self.move(*posicao_salva)

        self.atualizar()

    def _alternar_modo(self):
        self._modo_total = not self._modo_total
        self._reconstruir_barra()

    def atualizar(self):
        """Chamado pelo QTimer de polling (ver app.py) e depois de fechar o
        diálogo de uma categoria (pra refletir o que foi marcado como visto)."""
        self._categorias = self._provider.listar_categorias()
        self._reconstruir_barra()

    def _reconstruir_barra(self):
        for botao in self._botoes_categoria:
            self._layout.removeWidget(botao)
            botao.deleteLater()
        self._botoes_categoria = []

        for categoria in self._categorias:
            contagem = categoria.total if self._modo_total else categoria.novidades
            if contagem == 0:
                continue
            marca = "*" if categoria.novidades > 0 else ""
            botao = QPushButton(f"{categoria.nome_exibicao} {contagem}{marca}")
            botao.setFlat(True)
            botao.setCursor(Qt.PointingHandCursor)
            botao.setStyleSheet(self._estilo_botao(categoria.novidades > 0))
            botao.clicked.connect(lambda _checked=False, c=categoria: self._abrir_categoria(c))
            self._layout.addWidget(botao)
            self._botoes_categoria.append(botao)

        self.adjustSize()
        self._atualizar_mascara()

    @staticmethod
    def _estilo_botao(tem_novidade: bool) -> str:
        cor = "#ffbe3c" if tem_novidade else "#ebebf0"
        peso = "bold" if tem_novidade else "normal"
        return (
            "QPushButton { background: transparent; border: none; padding: 4px 8px; "
            f"color: {cor}; font-weight: {peso}; }}"
        )

    def _abrir_categoria(self, categoria):
        dialogo = DialogoCategoria(categoria, self._provider, self)
        dialogo.exec()
        self.atualizar()

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        caminho = QPainterPath()
        caminho.addRoundedRect(self.rect(), RAIO_CANTO, RAIO_CANTO)
        pintor.fillPath(caminho, COR_FUNDO)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._atualizar_mascara()

    def _atualizar_mascara(self):
        caminho = QPainterPath()
        caminho.addRoundedRect(self.rect(), RAIO_CANTO, RAIO_CANTO)
        self.setMask(QRegion(caminho.toFillPolygon().toPolygon()))

    def mousePressEvent(self, evento):
        self._pos_pressionada = evento.globalPosition().toPoint()

    def mouseMoveEvent(self, evento):
        if self._pos_pressionada is None:
            return
        atual = evento.globalPosition().toPoint()
        self.move(self.pos() + (atual - self._pos_pressionada))
        self._pos_pressionada = atual

    def mouseReleaseEvent(self, evento):
        self._pos_pressionada = None
        self._persistencia.salvar_posicao_janela(self.x(), self.y())

    def closeEvent(self, evento):
        self._persistencia.salvar_posicao_janela(self.x(), self.y())
        super().closeEvent(evento)


class DialogoCategoria(QDialog):
    """Lista de tickets de UMA categoria - o "drill-down" ao clicar num número
    da barra. "Abrir" manda pro Jira de verdade E marca como visto (é isso que
    limpa a novidade, nunca só ter aberto esta lista - ver ARQUITETURA.md)."""

    def __init__(self, categoria, provider, parent=None):
        super().__init__(parent)
        self.setWindowTitle(categoria.nome_exibicao)
        self._provider = provider

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{categoria.nome_exibicao} ({categoria.total})"))

        area = QScrollArea()
        area.setWidgetResizable(True)
        conteudo = QWidget()
        conteudo_layout = QVBoxLayout(conteudo)
        for ticket in categoria.tickets:
            conteudo_layout.addWidget(self._linha_ticket(ticket))
        conteudo_layout.addStretch()
        area.setWidget(conteudo)
        layout.addWidget(area)

    def _linha_ticket(self, ticket) -> QWidget:
        linha = QWidget()
        linha_layout = QHBoxLayout(linha)
        linha_layout.setContentsMargins(0, 0, 0, 0)

        texto = QLabel(f"{ticket.chave} | {ticket.resumo}" + (" ● NOVO" if ticket.novo else ""))
        if ticket.novo:
            fonte = texto.font()
            fonte.setBold(True)
            texto.setFont(fonte)
        linha_layout.addWidget(texto, 1)

        botao_abrir = QPushButton("Abrir")
        botao_abrir.clicked.connect(lambda: self._abrir(ticket))
        linha_layout.addWidget(botao_abrir)
        return linha

    def _abrir(self, ticket):
        webbrowser.open(ticket.url)
        self._provider.marcar_visto(ticket.chave)
        ticket.novo = False
