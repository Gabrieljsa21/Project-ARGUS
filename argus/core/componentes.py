"""Componentes visuais reaproveitáveis do Argus, no padrão da GAIA: tarefa
em segundo plano, botão, título/descrição de seção, spinbox em cápsula e
switch. Saíram de `widget.py` (2026-11-12) pra ele ficar só com a janela
principal e o painel de detalhes."""

import threading
import traceback

from PySide6.QtCore import (
    QObject, Qt, QTimer, QThread, Signal, QPoint, QRect, QSize, QPropertyAnimation, QEasingCurve, Property,
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QIntValidator,
)
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QLineEdit, QCheckBox,
)

from .tema import (
    BG_COLOR, SURFACE_COLOR, HIGHLIGHT_COLOR, BORDA_SUTIL,
    GAIA_GOLD, GAIA_GOLD_HOVER, TEXT_COLOR, TEXT_DIM, FONTE_BASE, cor_com_alpha,
)


# Compartilhadas com widget.py e dialogos.py.
TAMANHO_FONTE_DETALHE = 11
LIMITE_JANELAS_DESTACADAS_PADRAO = 5
# Padrão de fábrica da chacoalhada de atenção, antes de qualquer config salva
# (ligável pelo menu de Configurações).
ATIVAR_CHACOALHADA_ATENCAO = False


class _TarefaSegundoPlano(QThread):
    """QThread genérica (2026-08-15) - roda `func` fora da thread da UI, pra
    não travar a janela durante uma chamada de rede (buscar comentários) ou de
    LLM (gerar o rascunho de análise). `concluido`/`erro` disparam de volta na
    thread da UI (padrão normal de sinal do Qt entre threads).

    O traceback completo vai pro log (2026-11-12) - antes só a mensagem curta
    chegava em `erro`, e um bug de verdade ficava indistinguível de rede."""
    concluido = Signal(object)
    erro = Signal(str)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func

    def run(self):
        try:
            resultado = self._func()
        except Exception as e:
            print(f"[Argus] Erro em segundo plano:\n{traceback.format_exc()}")
            self.erro.emit(str(e))
        else:
            self.concluido.emit(resultado)


class _PonteSegundoPlano(QObject):
    concluido = Signal(object)
    erro = Signal(str)


# Pontes vivas: sem referência, o Python apagaria a ponte antes do sinal chegar.
_pontes_ativas = set()


def executar_em_segundo_plano(func, ao_concluir=None, ao_falhar=None) -> None:
    """Roda `func` numa thread daemon do Python e chama `ao_concluir(resultado)`
    ou `ao_falhar(mensagem)` de volta na thread da UI (sinal entre threads).

    🔥 Diferente de `_TarefaSegundoPlano` (2026-11-12): uma QThread ainda
    rodando quando o processo termina aborta o Python inteiro ("QThread:
    Destroyed while thread is still running"). Pra gravações curtas
    disparadas por clique (marcar como visto), fechar o Argus no meio não
    pode derrubar nada - a thread daemon simplesmente morre junto."""
    ponte = _PonteSegundoPlano()
    _pontes_ativas.add(ponte)

    def _finalizar():
        _pontes_ativas.discard(ponte)
        ponte.deleteLater()

    ponte.concluido.connect(lambda resultado: (ao_concluir and ao_concluir(resultado), _finalizar()))
    ponte.erro.connect(lambda mensagem: (ao_falhar and ao_falhar(mensagem), _finalizar()))

    def _rodar():
        try:
            resultado = func()
        except Exception as e:
            print(f"[Argus] Erro em segundo plano:\n{traceback.format_exc()}")
            ponte.erro.emit(str(e))
        else:
            ponte.concluido.emit(resultado)

    threading.Thread(target=_rodar, daemon=True, name="argus-segundo-plano").start()


def _botao_estilizado(texto, cor=GAIA_GOLD, preenchido=False) -> QPushButton:
    """Botão no PADRÃO VISUAL DA GAIA (2026-08-16, pedido do usuário: "os
    botões eu quero eles no padrão da GAIA. A GAIA vai ser o padrão de todos
    os projetos") - mesmo molde de `criar_botao` (assistant/ui/qt_widgets.py):
    `preenchido=True` pro botão de ação PRINCIPAL (fundo dourado sólido, ex.:
    "Salvar", "Analisar", "Entendi"); `False` (padrão) pro estilo "outline"
    dos botões secundários (ex.: "Cancelar", "Abrir", "Fechar"). O Argus
    continua sem IMPORTAR a fábrica de widgets da GAIA (fica standalone/leve
    pros colegas, ver docstring do módulo) - só copia o visual."""
    botao = QPushButton(texto)
    botao.setCursor(Qt.PointingHandCursor)
    botao.setFixedHeight(32)
    botao.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_DETALHE, QFont.Bold))
    if preenchido:
        botao.setStyleSheet(f"""
            QPushButton {{
                background-color: {GAIA_GOLD}; color: {BG_COLOR};
                border: none; border-radius: 8px; padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: {GAIA_GOLD_HOVER}; }}
        """)
    else:
        botao.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_COLOR}; color: {cor};
                border: 1px solid {BORDA_SUTIL}; border-radius: 8px; padding: 0 14px;
            }}
            QPushButton:hover {{ background-color: {HIGHLIGHT_COLOR}; }}
        """)
    return botao



def _titulo_secao(texto, cor=GAIA_GOLD, tamanho=13) -> QLabel:
    """Título de seção/card no padrão da GAIA (`criar_titulo_secao`,
    assistant/ui/qt_widgets.py) - copiado aqui (não importado, ver docstring
    do módulo)."""
    lbl = QLabel(texto)
    lbl.setFont(QFont(FONTE_BASE, tamanho, QFont.Bold))
    lbl.setStyleSheet(f"color: {cor}; background: transparent; border: none;")
    return lbl


def _descricao(texto) -> QLabel:
    """Texto explicativo discreto no padrão da GAIA (`criar_descricao`)."""
    lbl = QLabel(texto)
    lbl.setWordWrap(True)
    lbl.setFont(QFont(FONTE_BASE, 10))
    lbl.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
    return lbl


class _CampoValorSpinbox(QLineEdit):
    """Campo de número da `SpinboxCapsula` - mesmo padrão da GAIA
    (`ui/qt_widgets.py`, pedido do usuário: "esses campos tem de permitir
    clicar nele para escrever"). Seleciona o texto inteiro ao focar
    (`QTimer.singleShot(0, ...)` - selecionar direto dentro do próprio
    `focusInEvent` não pega, o clique que deu o foco ainda vai processar seu
    próprio posicionamento de cursor por cima logo em seguida)."""

    def focusInEvent(self, evento):
        super().focusInEvent(evento)
        QTimer.singleShot(0, self.selectAll)


class SpinboxCapsula(QWidget):
    """Campo numérico "Cápsula" no padrão da GAIA (2026-08-16, pedido do
    usuário: "os botões eu quero eles no padrão da GAIA" - copiado de
    `ui/qt_widgets.py`, não importado, ver docstring do módulo) - botões +/-
    redondos dentro de uma cápsula arredondada, em vez das setinhas nativas
    do `QSpinBox` (pequenas demais pra acertar o clique com facilidade).
    Expõe a mesma interface básica de um `QSpinBox` (`value()`/`setValue()`/
    `setRange()`/`valueChanged`)."""

    valueChanged = Signal(int)

    _TAMANHO_BOTAO = 20

    def __init__(self, minimo, maximo, valor_atual, largura=None, passo=1, parent=None):
        super().__init__(parent)
        self._minimo = minimo
        self._maximo = maximo
        self._passo = passo
        self._valor = max(minimo, min(maximo, valor_atual))

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("SpinboxCapsula")
        self.setFixedHeight(self._TAMANHO_BOTAO + 6)
        self.setFixedWidth(self._largura_minima_necessaria(largura))
        self.setStyleSheet(f"""
            QWidget#SpinboxCapsula {{
                background-color: {HIGHLIGHT_COLOR};
                border: 1px solid {BORDA_SUTIL};
                border-radius: {(self._TAMANHO_BOTAO + 6) // 2}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        self._botao_menos = self._criar_botao("−", self._decrementar)
        self._campo_valor = _CampoValorSpinbox(str(self._valor))
        self._campo_valor.setAlignment(Qt.AlignCenter)
        self._campo_valor.setFrame(False)
        self._campo_valor.setValidator(QIntValidator(self._minimo, self._maximo, self._campo_valor))
        self._campo_valor.setStyleSheet(f"""
            QLineEdit {{
                color: {TEXT_COLOR}; font-family: Consolas; font-size: 12px;
                border: none; background: transparent; padding: 0px;
            }}
        """)
        self._campo_valor.editingFinished.connect(self._ao_editar_texto)
        self._botao_mais = self._criar_botao("+", self._incrementar)

        layout.addWidget(self._botao_menos)
        layout.addWidget(self._campo_valor, stretch=1)
        layout.addWidget(self._botao_mais)

    def _largura_minima_necessaria(self, largura_pedida):
        texto_maior = str(max(abs(self._minimo), abs(self._maximo)))
        if self._minimo < 0:
            texto_maior = "-" + texto_maior
        largura_texto = QFontMetrics(QFont("Consolas", 12)).horizontalAdvance(texto_maior)
        minima = self._TAMANHO_BOTAO * 2 + 6 + 4 + largura_texto + 14
        return max(largura_pedida or 0, minima)

    def _criar_botao(self, texto, ao_clicar):
        botao = QPushButton(texto)
        botao.setFixedSize(self._TAMANHO_BOTAO, self._TAMANHO_BOTAO)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {TEXT_DIM};
                border: none; border-radius: {self._TAMANHO_BOTAO // 2}px;
                font-size: 14px; font-weight: 600; padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {cor_com_alpha(GAIA_GOLD, 0.18)}; color: {GAIA_GOLD};
            }}
        """)
        botao.clicked.connect(ao_clicar)
        return botao

    def _decrementar(self, checked=False):
        self.setValue(self._valor - self._passo)

    def _incrementar(self, checked=False):
        self.setValue(self._valor + self._passo)

    def _ao_editar_texto(self):
        try:
            novo_valor = int(self._campo_valor.text().strip())
        except ValueError:
            novo_valor = self._valor
        self.setValue(novo_valor)

    def value(self):
        return self._valor

    def setValue(self, novo_valor):
        novo_valor = max(self._minimo, min(self._maximo, novo_valor))
        mudou = novo_valor != self._valor
        self._valor = novo_valor
        self._campo_valor.setText(str(novo_valor))
        if mudou:
            self.valueChanged.emit(novo_valor)

    def setRange(self, minimo, maximo):
        self._minimo = minimo
        self._maximo = maximo
        self.setValue(self._valor)


COR_BOLINHA_SWITCH_LIGADO = HIGHLIGHT_COLOR
COR_BOLINHA_SWITCH_DESLIGADO = TEXT_COLOR


class Switch(QCheckBox):
    """Toggle animado (trilho + bolinha deslizando) no padrão da GAIA
    (2026-08-16, pedido do usuário: "eu prefiro toggle do q checkbox" -
    copiado de `ui/qt_widgets.py`, não importado, ver docstring do módulo) -
    usado pra qualquer configuração liga/desliga (ex.: chacoalhada de
    atenção), em vez de um `QCheckBox` nativo."""

    def __init__(self, texto_on, texto_off, cor=GAIA_GOLD, marcado=False,
                 cor_bolinha_ligado=COR_BOLINHA_SWITCH_LIGADO,
                 cor_bolinha_desligado=COR_BOLINHA_SWITCH_DESLIGADO, parent=None):
        super().__init__(parent)
        self.texto_on = texto_on
        self.texto_off = texto_off
        self.cor = QColor(cor)
        self.cor_bolinha_ligado = QColor(cor_bolinha_ligado)
        self.cor_bolinha_desligado = QColor(cor_bolinha_desligado)
        self._pos_bolinha = 1.0 if marcado else 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setChecked(marcado)
        self.setText(texto_on if marcado else texto_off)
        self.setFont(QFont(FONTE_BASE, 11))
        self.stateChanged.connect(self._ao_mudar_estado)

        self._anim = QPropertyAnimation(self, b"pos_bolinha")
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _obter_pos_bolinha(self):
        return self._pos_bolinha

    def _definir_pos_bolinha(self, valor):
        self._pos_bolinha = valor
        self.update()

    pos_bolinha = Property(float, _obter_pos_bolinha, _definir_pos_bolinha)

    def _ao_mudar_estado(self, estado):
        marcado = bool(estado)
        self.setText(self.texto_on if marcado else self.texto_off)
        self._anim.stop()
        self._anim.setStartValue(self._pos_bolinha)
        self._anim.setEndValue(1.0 if marcado else 0.0)
        self._anim.start()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def sizeHint(self):
        fm = self.fontMetrics()
        largura_maior_texto = max(fm.horizontalAdvance(self.texto_on), fm.horizontalAdvance(self.texto_off))
        return QSize(46 + 8 + largura_maior_texto, 26)

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        largura_trilho, altura_trilho = 42, 21
        y_trilho = (26 - altura_trilho) / 2
        cor_trilho = self.cor if self.isChecked() else QColor(HIGHLIGHT_COLOR)
        pintor.setBrush(cor_trilho)
        pintor.setPen(Qt.NoPen)
        pintor.drawRoundedRect(0, int(y_trilho), largura_trilho, altura_trilho, altura_trilho / 2, altura_trilho / 2)

        raio_bolinha = altura_trilho / 2 - 2
        x_bolinha = 2 + raio_bolinha + self._pos_bolinha * (largura_trilho - altura_trilho)
        cor_bolinha = self.cor_bolinha_ligado if self.isChecked() else self.cor_bolinha_desligado
        pintor.setBrush(cor_bolinha)
        pintor.drawEllipse(QPoint(int(x_bolinha), int(y_trilho + altura_trilho / 2)), int(raio_bolinha), int(raio_bolinha))

        x_texto = largura_trilho + 8
        pintor.setPen(QColor(TEXT_COLOR))
        pintor.setFont(self.font())
        pintor.drawText(QRect(x_texto, 0, self.width() - x_texto, 26), Qt.AlignVCenter | Qt.AlignLeft, self.text())


