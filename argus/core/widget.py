"""Janela principal do Argus - sempre no topo, transparente, sem borda,
arrastável (ver ARQUITETURA.md, seção "Janela"). Não sabe o que é Jira - só
fala com `NotificacaoProvider`/`Persistencia`.

🔥 Redesenho (2026-08-14, pedido do usuário depois de ver a v1 rodando: "ficou
bem feio... parecem dois programas diferentes") - a lista de tickets era um
QDialog separado, com barra de título nativa do Windows, destoando da barra
translúcida. Agora é TUDO uma janela só: painel embutido embaixo da barra,
abre com HOVER numa categoria (não clique), fecha 250ms depois do mouse sair
de toda a área (chip + painel contam como uma área contínua de hover - por
isso o `_AreaComHover` compartilhado), clique numa categoria FIXA o painel
aberto até clicar de novo. Paleta copiada do Painel da GAIA (`core/tema.py`).

A personagem/animação continua opcional e decorativa - `_Alavanca` é só o
lugar-reservado dela (clique alterna novidades/total, arrastar move a
janela)."""

import webbrowser

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QColor, QRegion, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea

from .tema import (
    SURFACE_COLOR, HIGHLIGHT_COLOR, BORDA_SUTIL,
    GAIA_GOLD, GAIA_SILVER, TEXT_COLOR, TEXT_DIM, FONTE_BASE,
)

LIMIAR_ARRASTAR_PIXELS = 6
ATRASO_FECHAR_MS = 250
RAIO_CANTO = 12
MAX_LINHAS_VISIVEIS = 5
ALTURA_LINHA = 30


class _Alavanca(QWidget):
    """Placeholder do lugar da personagem - widget PRÓPRIO (não QPushButton
    comum) porque precisa diferenciar clique de arrastar no mesmo gesto de
    mouse. Clique alterna novidades/total; arrastar move a janela inteira."""

    def __init__(self, ao_clicar, ao_soltar_arraste, parent=None):
        super().__init__(parent)
        self._ao_clicar = ao_clicar
        self._ao_soltar_arraste = ao_soltar_arraste
        self._pos_pressionada = None
        self._arrastou = False
        self.setFixedSize(24, 24)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        pintor.setBrush(QColor(GAIA_GOLD))
        pintor.setPen(Qt.NoPen)
        pintor.drawEllipse(1, 1, 22, 22)

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
        if self._arrastou:
            self._ao_soltar_arraste()
        else:
            self._ao_clicar()
        self._pos_pressionada = None


class _AreaComHover(QWidget):
    """QWidget genérico que avisa quando o mouse entra/sai - usado tanto pelos
    chips de categoria quanto pelo painel de baixo, pra tratar os dois como
    UMA área contínua (mover o mouse do chip pro painel não deve fechar
    nada - só sair de AMBOS agenda o fechamento, ver ArgusWidget)."""

    def __init__(self, ao_entrar, ao_sair, parent=None):
        super().__init__(parent)
        self._ao_entrar = ao_entrar
        self._ao_sair = ao_sair

    def enterEvent(self, evento):
        self._ao_entrar()
        super().enterEvent(evento)

    def leaveEvent(self, evento):
        self._ao_sair()
        super().leaveEvent(evento)


class _ChipCategoria(_AreaComHover):
    """Cápsula de UMA categoria na barra - bolinha de estado (dourada se tem
    novidade, prateada se não) + nome + badge com o contador. Hover chama
    `ao_entrar_categoria(categoria)`; clique fixa/desfixa o painel."""

    def __init__(self, categoria, contagem, tem_novidade, ao_entrar_categoria, ao_sair, ao_clicar, parent=None):
        super().__init__(lambda: ao_entrar_categoria(categoria), ao_sair, parent)
        self.categoria = categoria
        self._ao_clicar = ao_clicar
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(6)

        cor_bolinha = GAIA_GOLD if tem_novidade else GAIA_SILVER
        bolinha = QLabel("●")
        bolinha.setStyleSheet(f"color: {cor_bolinha}; background: transparent; border: none; font-size: 8px;")
        layout.addWidget(bolinha)

        nome = QLabel(categoria.nome_exibicao)
        nome.setFont(QFont(FONTE_BASE, 9))
        nome.setStyleSheet(f"color: {TEXT_COLOR}; background: transparent; border: none;")
        layout.addWidget(nome)

        cor_badge = GAIA_GOLD if tem_novidade else HIGHLIGHT_COLOR
        cor_texto_badge = SURFACE_COLOR if tem_novidade else TEXT_DIM
        badge = QLabel(str(contagem))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(17)
        badge.setMinimumWidth(17)
        fonte_badge = QFont(FONTE_BASE, 8, QFont.Bold)
        badge.setFont(fonte_badge)
        badge.setStyleSheet(
            f"background-color: {cor_badge}; color: {cor_texto_badge}; "
            "border-radius: 8px; padding: 0px 5px;"
        )
        layout.addWidget(badge)

        self.definir_aberta(False)

    def definir_aberta(self, aberta: bool):
        cor_fundo = HIGHLIGHT_COLOR if aberta else "transparent"
        cor_borda = GAIA_GOLD if aberta else "transparent"
        self.setStyleSheet(
            f"_ChipCategoria {{ background-color: {cor_fundo}; border: 1px solid {cor_borda}; border-radius: 14px; }}"
        )

    def mousePressEvent(self, evento):
        self._ao_clicar(self.categoria)


class ArgusWidget(QWidget):
    def __init__(self, provider, persistencia):
        super().__init__()
        self._provider = provider
        self._persistencia = persistencia
        self._modo_total = False
        self._categorias = []
        self._chips = []
        self._chave_categoria_aberta = None
        self._fixado = False

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        self._barra = QWidget()
        self._layout_barra = QHBoxLayout(self._barra)
        self._layout_barra.setContentsMargins(10, 6, 10, 6)
        self._layout_barra.setSpacing(4)
        self._alavanca = _Alavanca(self._alternar_modo, self._persistir_posicao, self._barra)
        self._layout_barra.addWidget(self._alavanca)
        layout_raiz.addWidget(self._barra)

        self._painel = _AreaComHover(self._cancelar_fechar, self._agendar_fechar, self)
        self._layout_painel = QVBoxLayout(self._painel)
        self._layout_painel.setContentsMargins(12, 8, 12, 10)
        self._layout_painel.setSpacing(6)
        self._painel.setVisible(False)
        layout_raiz.addWidget(self._painel)

        self._timer_fechar = QTimer(self)
        self._timer_fechar.setSingleShot(True)
        self._timer_fechar.setInterval(ATRASO_FECHAR_MS)
        self._timer_fechar.timeout.connect(self._fechar_painel_se_nao_fixado)

        posicao_salva = self._persistencia.obter_posicao_janela()
        if posicao_salva:
            self.move(*posicao_salva)

        self.atualizar()

    # --- ciclo de dado -----------------------------------------------------

    def atualizar(self):
        """Chamado pelo QTimer de polling (ver app.py) e depois de abrir um
        ticket (pra refletir o que foi marcado como visto)."""
        self._categorias = self._provider.listar_categorias()
        self._reconstruir_barra()
        if self._chave_categoria_aberta:
            categoria = self._categoria_por_chave(self._chave_categoria_aberta)
            contagem_atual = (categoria.total if self._modo_total else categoria.novidades) if categoria else 0
            if categoria and contagem_atual > 0:
                self._preencher_painel(categoria)
            else:
                self._fechar_painel()

    def _categoria_por_chave(self, chave):
        return next((c for c in self._categorias if c.chave == chave), None)

    def _alternar_modo(self):
        self._modo_total = not self._modo_total
        self._reconstruir_barra()

    # --- barra de categorias -------------------------------------------------

    def _reconstruir_barra(self):
        for chip in self._chips:
            self._layout_barra.removeWidget(chip)
            chip.deleteLater()
        self._chips = []

        for categoria in self._categorias:
            contagem = categoria.total if self._modo_total else categoria.novidades
            if contagem == 0:
                continue
            chip = _ChipCategoria(
                categoria, contagem, categoria.novidades > 0,
                ao_entrar_categoria=self._hover_entrou_categoria,
                ao_sair=self._agendar_fechar,
                ao_clicar=self._categoria_clicada,
                parent=self._barra,
            )
            chip.definir_aberta(categoria.chave == self._chave_categoria_aberta)
            self._layout_barra.addWidget(chip)
            self._chips.append(chip)

        self._ajustar_tamanho()

    # --- hover/fixar do painel ----------------------------------------------

    def _cancelar_fechar(self):
        self._timer_fechar.stop()

    def _agendar_fechar(self):
        self._timer_fechar.start()

    def _hover_entrou_categoria(self, categoria):
        self._cancelar_fechar()
        self._mostrar_categoria(categoria)

    def _categoria_clicada(self, categoria):
        if self._fixado and self._chave_categoria_aberta == categoria.chave:
            self._fixado = False
            self._agendar_fechar()
        else:
            self._fixado = True
            self._mostrar_categoria(categoria)

    def _fechar_painel_se_nao_fixado(self):
        if not self._fixado:
            self._fechar_painel()

    def _mostrar_categoria(self, categoria):
        self._chave_categoria_aberta = categoria.chave
        for chip in self._chips:
            chip.definir_aberta(chip.categoria.chave == categoria.chave)
        self._preencher_painel(categoria)
        self._painel.setVisible(True)
        self._ajustar_tamanho()

    def _fechar_painel(self):
        self._chave_categoria_aberta = None
        self._fixado = False
        for chip in self._chips:
            chip.definir_aberta(False)
        self._painel.setVisible(False)
        self._ajustar_tamanho()

    def _ajustar_tamanho(self):
        """🔥 Correção (2026-08-14, achado testando: "acontece quando uma
        janela com vários itens está aberta e eu vou para uma com poucos") -
        `adjustSize()` (mesmo precedido de `resize(1, 1)`) simplesmente NÃO
        encolhe esta janela de volta depois de ter ficado grande uma vez -
        confirmado com um teste isolado: `sizeHint()` já calculava o tamanho
        pequeno certinho, mas `adjustSize()` mantinha o tamanho antigo mesmo
        assim (limitação real do Qt em janelas sem borda/com máscara -
        `adjustSize()` normalmente só é confiável fazendo `resize(sizeHint())`
        por baixo, e por algum motivo não fez isso aqui). `resize(sizeHint())`
        EXPLÍCITO funciona - é isso que fica.

        Só que mesmo com `layout().activate()` antes, `sizeHint()` chamado NO
        MESMO instante de `_preencher_painel` (que acabou de tirar/pôr
        widgets) ainda vinha errado (confirmado testando: widgets recém-
        adicionados a um layout de uma janela JÁ visível não têm o tamanho
        real calculado até o Qt processar isso pela fila de eventos - nem
        `activate()` força isso adiantado). Por isso o `resize()` de verdade
        só acontece 1 volta do event loop depois (`QTimer.singleShot(0, ...)`),
        quando o Qt já processou tudo - é o jeito robusto, não um hack."""
        QTimer.singleShot(0, self._aplicar_tamanho_real)

    def _aplicar_tamanho_real(self):
        self.resize(self.sizeHint())
        self._atualizar_mascara()

    # --- conteúdo do painel --------------------------------------------------

    def _preencher_painel(self, categoria):
        """🔥 Correção (2026-08-14, achado testando: "acontece quando uma janela
        com vários itens está aberta e eu vou para uma com poucos") - antes,
        TODA categoria (mesmo com 1 ticket) ganhava um `QScrollArea` com altura
        calculada + `addStretch()` dentro - o stretch reservava espaço extra
        e, ao trocar de uma categoria grande pra uma pequena, a janela não
        encolhia de volta (Qt não recalcula sozinho o sizeHint de um
        QScrollArea depois que ele já foi maior uma vez). Agora só existe
        QScrollArea quando REALMENTE precisa rolar (mais tickets que
        MAX_LINHAS_VISIVEIS) - sem isso, cada linha ocupa só o próprio
        tamanho, sem stretch nenhum, e a janela encolhe corretamente porque
        nunca ficou com um widget "elástico" registrado no layout."""
        while self._layout_painel.count():
            item = self._layout_painel.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        largura = max(self._barra.sizeHint().width(), 260)

        cabecalho = QLabel(f"{categoria.nome_exibicao} ({categoria.total})")
        cabecalho.setFont(QFont(FONTE_BASE, 8))
        cabecalho.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        self._layout_painel.addWidget(cabecalho)

        if not categoria.tickets:
            vazio = QLabel("Nada por aqui.")
            vazio.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
            self._layout_painel.addWidget(vazio)
            return

        if len(categoria.tickets) <= MAX_LINHAS_VISIVEIS:
            for ticket in categoria.tickets:
                self._layout_painel.addWidget(self._linha_ticket(ticket, largura))
            return

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setStyleSheet("background: transparent; border: none;")
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setFixedWidth(largura)
        area.setFixedHeight(MAX_LINHAS_VISIVEIS * ALTURA_LINHA)

        conteudo = QWidget()
        conteudo.setStyleSheet("background: transparent;")
        layout_lista = QVBoxLayout(conteudo)
        layout_lista.setContentsMargins(0, 0, 0, 0)
        layout_lista.setSpacing(2)
        layout_lista.setAlignment(Qt.AlignTop)
        for ticket in categoria.tickets:
            layout_lista.addWidget(self._linha_ticket(ticket, largura))
        area.setWidget(conteudo)

        self._layout_painel.addWidget(area)

    def _linha_ticket(self, ticket, largura_disponivel) -> QWidget:
        linha = QWidget()
        linha.setFixedHeight(ALTURA_LINHA - 4)
        layout_linha = QHBoxLayout(linha)
        layout_linha.setContentsMargins(4, 2, 4, 2)
        layout_linha.setSpacing(8)

        peso = QFont.Bold if ticket.novo else QFont.Normal
        fonte = QFont(FONTE_BASE, 9, peso)
        cor_texto = TEXT_COLOR if ticket.novo else TEXT_DIM
        sufixo = " ● NOVO" if ticket.novo else ""
        texto_bruto = f"{ticket.chave} | {ticket.resumo}{sufixo}"

        metricas = QFontMetrics(fonte)
        texto_elidido = metricas.elidedText(texto_bruto, Qt.ElideRight, largura_disponivel - 60)

        texto = QLabel(texto_elidido)
        texto.setFont(fonte)
        texto.setStyleSheet(f"color: {cor_texto}; background: transparent; border: none;")
        layout_linha.addWidget(texto, 1)

        abrir = QLabel("↗")
        abrir.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none; font-size: 13px;")
        abrir.setCursor(Qt.PointingHandCursor)
        abrir.mousePressEvent = lambda evento, t=ticket: self._abrir_ticket(t)
        layout_linha.addWidget(abrir)

        return linha

    def _abrir_ticket(self, ticket):
        webbrowser.open(ticket.url)
        self._provider.marcar_visto(ticket.chave)
        self.atualizar()

    # --- janela (pintura/máscara/posição) -------------------------------------

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        caminho = QPainterPath()
        caminho.addRoundedRect(self.rect(), RAIO_CANTO, RAIO_CANTO)
        cor_fundo = QColor(SURFACE_COLOR)
        cor_fundo.setAlpha(235)
        pintor.fillPath(caminho, cor_fundo)
        pintor.setPen(QColor(BORDA_SUTIL))
        pintor.drawPath(caminho)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._atualizar_mascara()

    def _atualizar_mascara(self):
        caminho = QPainterPath()
        caminho.addRoundedRect(self.rect(), RAIO_CANTO, RAIO_CANTO)
        self.setMask(QRegion(caminho.toFillPolygon().toPolygon()))

    def _persistir_posicao(self):
        self._persistencia.salvar_posicao_janela(self.x(), self.y())

    def closeEvent(self, evento):
        self._persistir_posicao()
        super().closeEvent(evento)
