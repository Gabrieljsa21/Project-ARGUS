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

import os
import webbrowser

from PySide6.QtCore import Qt, QTimer, QThread, Signal, QPointF, QEvent, QObject
from PySide6.QtGui import QPainter, QPainterPath, QPixmap, QColor, QRegion, QFont, QFontMetrics, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QStyleOption, QStyle, QApplication,
    QDialog, QTextEdit, QPlainTextEdit, QPushButton,
)

from .tema import (
    SURFACE_COLOR, HIGHLIGHT_COLOR, BORDA_SUTIL,
    GAIA_GOLD, GAIA_SILVER, TEXT_COLOR, TEXT_DIM, FONTE_BASE, CORES_PRIORIDADE,
)
from .win32_dwm import aplicar_cantos_redondos, aplicar_mica, aplicar_acrylic, remover_cor_borda

LIMIAR_ARRASTAR_PIXELS = 6
ATRASO_FECHAR_MS = 250
RAIO_CANTO = 12
MAX_LINHAS_VISIVEIS = 5
ALTURA_LINHA = 36
TAMANHO_FONTE_NOME = 11
TAMANHO_FONTE_BADGE = 10
TAMANHO_FONTE_TICKET = 11
TAMANHO_FONTE_CABECALHO = 9

# 🔥 Teste visual (2026-08-15, ver win32_dwm.aplicar_mica) - liga/desliga o
# fundo Mica nativo pra comparar lado a lado com o preenchimento sólido de
# sempre antes de decidir manter. Com Mica ativo, o preenchimento próprio usa
# bem menos alpha (ver ALPHA_FUNDO_COM_MICA) pra deixar o material aparecer.
# DESLIGADO (2026-08-15, pedido do usuário depois de ver rodando: "achei
# feio... prefiro cores escuras") - o material claro/acinzentado do Mica não
# combina com a identidade escura da GAIA. Função continua em win32_dwm.py,
# só não é mais chamada por padrão.
ATIVAR_MICA = False
ALPHA_FUNDO_SEM_MICA = 235
ALPHA_FUNDO_COM_MICA = 40

# 🔥 Acrylic escuro (2026-08-15) - diferente do Mica, testado visualmente com
# 3 níveis de tingimento (alpha 120/190/235) e ESCOLHIDO pelo usuário: alpha
# 120 (mais blur aparece, tingimento mais leve). Ligado por padrão - quando
# aplica de verdade (Windows 10+), o preenchimento próprio da janela é
# pulado inteiramente (ver paintEvent) pra deixar o blur nativo aparecer.
ATIVAR_ACRYLIC = True
ALPHA_ACRYLIC = 120

# 🔥 Anel pulsante (2026-08-15) - nasce no raio do badge de uma categoria com
# novidade, expande até EXPANSAO_ANEL (~160%) enquanto desaparece
# gradualmente, e reinicia - variante "A" escolhida pelo usuário entre as
# opções testadas (badge crescendo de tamanho foi descartado: "não quero que
# a badge aumente e diminua").
EXPANSAO_ANEL = 1.6
DURACAO_ANEL_MS = 1400
INTERVALO_TIMER_ANEL_MS = 30

CAMINHO_ICONE_ALAVANCA = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "assets", "icone_argus.png"
)

# 🔥 Painel de detalhes (2026-08-15, pedido do usuário: "quando clicar em um
# card, abra um modal a direita, com as informações mais detalhadas do
# ticket... botão pra abrir ticket e um pra analisar") - janela flutuante
# PRÓPRIA (não embutida na janela principal, ver ArgusWidget) posicionada ao
# lado, com espaço suficiente pra rótulo+valor sem elidir demais.
LARGURA_PAINEL_DETALHES = 340
ESPACAMENTO_PAINEL_DETALHES = 8
TAMANHO_FONTE_DETALHE = 11

# 🔥 Glow no chip aberto (2026-08-15) - variante "5c" escolhida: junto com o
# destaque já existente (fundo HIGHLIGHT_COLOR + borda dourada), um brilho
# suave por trás reforça visualmente qual categoria está aberta.
ALPHA_GLOW_ABERTA = 60


class _Alavanca(QWidget):
    """Placeholder do lugar da personagem - widget PRÓPRIO (não QPushButton
    comum) porque precisa diferenciar clique de arrastar no mesmo gesto de
    mouse. Clique alterna novidades/total; arrastar move a janela inteira."""

    _pixmap_icone = None

    def __init__(self, ao_clicar, ao_soltar_arraste, parent=None):
        super().__init__(parent)
        self._ao_clicar = ao_clicar
        self._ao_soltar_arraste = ao_soltar_arraste
        self._pos_pressionada = None
        self._arrastou = False
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)
        if _Alavanca._pixmap_icone is None:
            _Alavanca._pixmap_icone = QPixmap(CAMINHO_ICONE_ALAVANCA)

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        pintor.setRenderHint(QPainter.SmoothPixmapTransform)
        icone = self._pixmap_icone.scaled(
            30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        x = (self.width() - icone.width()) // 2
        y = (self.height() - icone.height()) // 2
        pintor.drawPixmap(x, y, icone)

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


class _RepassaRoda(QObject):
    """Filtro de evento instalado em TODOS os widgets descendentes da lista
    de tickets (varredura recursiva via `findChildren`, ver _preencher_painel)
    - sem isso, rolar o mouse em cima de qualquer texto/linha só funcionava
    quando o cursor estava bem em cima da barra de rolagem em si (achado real
    testando: "ainda não consigo usar o scroll em qualquer lugar dentro da
    janela"). Repassa manualmente pro viewport da área rolável - instalar em
    CADA descendente (não só no container) garante que nenhum widget
    intermediário consiga engolir o evento sem repassar."""

    def __init__(self, area_scroll, parent=None):
        super().__init__(parent)
        self._area_scroll = area_scroll

    def eventFilter(self, objeto, evento):
        if evento.type() == QEvent.Type.Wheel:
            QApplication.sendEvent(self._area_scroll.viewport(), evento)
            return True
        return False


class _ChipCategoria(_AreaComHover):
    """Cápsula de UMA categoria na barra - bolinha de estado (dourada se tem
    novidade, prateada se não) + nome + badge com o contador. Hover chama
    `ao_entrar_categoria(categoria)`; clique fixa/desfixa o painel.

    🔥 Anel pulsante + glow (2026-08-15, ver constantes no topo do arquivo) -
    `paintEvent` é sobrescrito aqui, então precisa desenhar o fundo/borda do
    QSS (`WA_StyledBackground`) manualmente via `QStyle.drawPrimitive` antes
    de mais nada - sem isso, sobrescrever `paintEvent` faz o destaque
    dourado de "aberta" parar de aparecer (pegadinha real do Qt: widget com
    `WA_StyledBackground` só pinta o QSS sozinho se NINGUÉM sobrescrever
    `paintEvent`)."""

    def __init__(self, categoria, contagem, tem_novidade, ao_entrar_categoria, ao_sair, ao_clicar, parent=None):
        super().__init__(lambda: ao_entrar_categoria(categoria), ao_sair, parent)
        self.categoria = categoria
        self._ao_clicar = ao_clicar
        self._tem_novidade = tem_novidade
        self._aberta = False
        self._fase_anel = 0.0
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 14, 9)
        layout.setSpacing(8)

        cor_bolinha = GAIA_GOLD if tem_novidade else GAIA_SILVER
        bolinha = QLabel("●")
        bolinha.setStyleSheet(f"color: {cor_bolinha}; background: transparent; border: none; font-size: 9px;")
        layout.addWidget(bolinha)

        nome = QLabel(categoria.nome_exibicao)
        nome.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_NOME))
        nome.setStyleSheet(f"color: {TEXT_COLOR}; background: transparent; border: none;")
        layout.addWidget(nome)

        cor_badge = GAIA_GOLD if tem_novidade else HIGHLIGHT_COLOR
        cor_texto_badge = SURFACE_COLOR if tem_novidade else TEXT_DIM
        fonte_badge = QFont(FONTE_BASE, TAMANHO_FONTE_BADGE, QFont.Bold)
        self._badge = QLabel(str(contagem))
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFont(fonte_badge)
        # 🔥 Correção (2026-08-15, achado testando: "o círculo se estica
        # horizontalmente") - largura só MÍNIMA (não fixa) deixava o Qt
        # esticar o badge quando sobrava espaço na barra (ex.: janela mais
        # larga por causa do painel aberto), virando uma "pílula" em vez de
        # círculo. Largura calculada pelo próprio texto (cabe "10"/"23" sem
        # cortar) e FIXADA de vez - nunca mais estica.
        metricas_badge = QFontMetrics(fonte_badge)
        largura_badge = max(21, metricas_badge.horizontalAdvance(str(contagem)) + 14)
        self._badge.setFixedSize(largura_badge, 21)
        self._badge.setStyleSheet(
            f"background-color: {cor_badge}; color: {cor_texto_badge}; "
            "border-radius: 10px;"
        )
        layout.addWidget(self._badge)

        self.definir_aberta(False)

        if tem_novidade:
            self._timer_anel = QTimer(self)
            self._timer_anel.timeout.connect(self._avancar_anel)
            self._timer_anel.start(INTERVALO_TIMER_ANEL_MS)

    def _avancar_anel(self):
        self._fase_anel += INTERVALO_TIMER_ANEL_MS / DURACAO_ANEL_MS
        if self._fase_anel >= 1.0:
            self._fase_anel -= 1.0
        self.update()

    def definir_aberta(self, aberta: bool):
        self._aberta = aberta
        cor_fundo = HIGHLIGHT_COLOR if aberta else "transparent"
        cor_borda = GAIA_GOLD if aberta else "transparent"
        self.setStyleSheet(
            f"_ChipCategoria {{ background-color: {cor_fundo}; border: 1px solid {cor_borda}; border-radius: 14px; }}"
        )
        self.update()

    def mousePressEvent(self, evento):
        self._ao_clicar(self.categoria)

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)

        opcao = QStyleOption()
        opcao.initFrom(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opcao, pintor, self)

        if self._aberta:
            pintor.save()
            caminho_clip = QPainterPath()
            caminho_clip.addRoundedRect(self.rect(), 14, 14)
            pintor.setClipPath(caminho_clip)
            centro = QPointF(self.width() / 2, self.height() / 2)
            gradiente = QRadialGradient(centro, max(self.width(), self.height()) * 0.8)
            cor_glow_inicio = QColor(GAIA_GOLD)
            cor_glow_inicio.setAlpha(ALPHA_GLOW_ABERTA)
            cor_glow_fim = QColor(GAIA_GOLD)
            cor_glow_fim.setAlpha(0)
            gradiente.setColorAt(0.0, cor_glow_inicio)
            gradiente.setColorAt(1.0, cor_glow_fim)
            pintor.fillRect(self.rect(), gradiente)
            pintor.restore()

        if self._tem_novidade:
            centro_badge = self._badge.mapTo(self, self._badge.rect().center())
            raio_base = self._badge.height() / 2
            raio_desejado = raio_base + (raio_base * (EXPANSAO_ANEL - 1.0)) * self._fase_anel

            # 🔥 Correção (2026-08-15, achado testando: "anel pulsante está
            # descentralizado") - o Qt SEMPRE corta qualquer desenho que
            # ultrapasse os limites do próprio widget (não tem como desligar
            # isso) - com o badge perto da borda do chip, o anel expandido
            # ficava cortado de um lado, parecendo torto/descentrado mesmo
            # com o centro matematicamente correto. Em vez de confiar só na
            # margem do layout (frágil - qualquer mudança de fonte/tamanho
            # podia voltar a cortar), limita o raio ao espaço de verdade
            # disponível até a borda mais próxima, medido a cada pintura.
            largura_pen = 2
            espaco_disponivel = min(
                centro_badge.x(), self.width() - centro_badge.x(),
                centro_badge.y(), self.height() - centro_badge.y(),
            ) - (largura_pen / 2 + 1)
            raio = min(raio_desejado, max(raio_base, espaco_disponivel))

            alpha = int(190 * (1.0 - self._fase_anel) ** 1.4)
            if alpha > 0:
                cor_anel = QColor(GAIA_GOLD)
                cor_anel.setAlpha(alpha)
                pintor.setPen(QPen(cor_anel, largura_pen))
                pintor.setBrush(Qt.NoBrush)
                pintor.drawEllipse(QPointF(centro_badge), raio, raio)


class _LinhaTicket(QWidget):
    """Uma linha de ticket na lista - campo INTEIRO clicável, com destaque
    sutil ao passar o mouse. Clique abre o painel de detalhes (2026-08-15,
    pedido do usuário - ver `ArgusWidget._ticket_clicado`/`_PainelDetalhesTicket`),
    não mais o navegador direto - abrir o link virou um botão dentro do
    painel. Sem ícone/botão separado no final (2026-08-15, pedido do usuário:
    "acho desnecessário esse botão... coloca o efeito dela no próprio campo da
    lista") - hover + cursor de mão já comunicam que a linha inteira é
    clicável, sem precisar de um alvo pequeno separado."""

    def __init__(self, ticket, resumo_elidido, fonte, ao_clicar, parent=None):
        super().__init__(parent)
        self._ticket = ticket
        self._ao_clicar = ao_clicar
        self._hover = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(ALTURA_LINHA - 4)

        layout_linha = QHBoxLayout(self)
        layout_linha.setContentsMargins(8, 3, 8, 3)

        cor_texto = TEXT_COLOR if ticket.novo else TEXT_DIM
        cor_prioridade = CORES_PRIORIDADE.get(ticket.prioridade, cor_texto)

        # 🔥 Cor por prioridade (2026-08-15, pedido do usuário: "a cor da fonte
        # representa exclusivamente a prioridade cadastrada no Jira") - só no
        # código (rich text HTML no QLabel), o resumo continua na cor normal
        # de sempre pra não virar uma parede de cor e perder legibilidade. Sem
        # escrever o NOME da prioridade (2026-08-15, "não precisa escrever
        # prioridade no nome, já tem legenda das cores") - a cor sozinha já
        # basta, a legenda no topo do painel explica o que cada uma significa.
        prefixo = QLabel(
            f'<span style="color:{cor_texto};">[{ticket.pontuacao_foco}]</span> '
            f'<span style="color:{cor_prioridade};">{ticket.chave}</span>'
        )
        prefixo.setTextFormat(Qt.RichText)
        prefixo.setFont(fonte)
        prefixo.setStyleSheet("background: transparent; border: none;")
        layout_linha.addWidget(prefixo)

        resumo = QLabel(resumo_elidido)
        resumo.setFont(fonte)
        resumo.setStyleSheet(f"color: {cor_texto}; background: transparent; border: none;")
        layout_linha.addWidget(resumo, 1)

        self._atualizar_estilo()

    def _atualizar_estilo(self):
        cor_fundo = HIGHLIGHT_COLOR if self._hover else "transparent"
        cor_borda = GAIA_GOLD if self._hover else "transparent"
        self.setStyleSheet(
            f"_LinhaTicket {{ background-color: {cor_fundo}; border: 1px solid {cor_borda}; border-radius: 8px; }}"
        )

    def enterEvent(self, evento):
        self._hover = True
        self._atualizar_estilo()
        super().enterEvent(evento)

    def leaveEvent(self, evento):
        self._hover = False
        self._atualizar_estilo()
        super().leaveEvent(evento)

    def mousePressEvent(self, evento):
        self._ao_clicar(self._ticket)


class _TarefaSegundoPlano(QThread):
    """QThread genérica (2026-08-15) - roda `func` fora da thread da UI, pra
    não travar a janela durante uma chamada de rede (buscar comentários) ou de
    LLM (gerar o rascunho de análise). `concluido`/`erro` disparam de volta na
    thread da UI (padrão normal de sinal do Qt entre threads)."""
    concluido = Signal(object)
    erro = Signal(str)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func

    def run(self):
        try:
            resultado = self._func()
        except Exception as e:
            self.erro.emit(str(e))
        else:
            self.concluido.emit(resultado)


def _botao_estilizado(texto, cor=GAIA_GOLD) -> QPushButton:
    """Botão mínimo próprio do Argus (2026-08-15) - o Argus não importa a
    fábrica de widgets da GAIA (fica standalone/leve pros colegas, ver
    docstring do módulo), então é um QPushButton simples com o mesmo
    tratamento visual de sempre (SURFACE_COLOR/hover) em vez de reaproveitar
    algo de fora do repositório."""
    botao = QPushButton(texto)
    botao.setCursor(Qt.PointingHandCursor)
    botao.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_DETALHE))
    botao.setStyleSheet(f"""
        QPushButton {{
            background-color: {SURFACE_COLOR}; color: {cor};
            border: 1px solid {BORDA_SUTIL}; border-radius: 8px; padding: 6px 12px;
        }}
        QPushButton:hover {{ background-color: {HIGHLIGHT_COLOR}; border-color: {cor}; }}
    """)
    return botao


class _DialogoComentario(QDialog):
    """Pergunta um comentário/instrução opcional ANTES de mandar o ticket pra
    análise (2026-08-15, pedido do usuário: "fazer a análise permitindo
    colocar um comentário") - texto livre, some direto na instrução da LLM
    (ver GAIA, quem injeta `analisar_ticket`), nunca vira comentário de
    verdade no Jira sozinho."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analisar ticket")
        self.setStyleSheet(f"background-color: {SURFACE_COLOR};")
        self.resize(360, 200)
        self.comentario = None

        lay = QVBoxLayout(self)
        rotulo = QLabel("Comentário/instrução adicional (opcional):")
        rotulo.setStyleSheet(f"color: {TEXT_DIM};")
        lay.addWidget(rotulo)

        self._campo = QPlainTextEdit()
        self._campo.setStyleSheet(
            f"background-color: {SURFACE_COLOR}; color: {TEXT_COLOR}; border: 1px solid {BORDA_SUTIL}; border-radius: 6px;"
        )
        lay.addWidget(self._campo, 1)

        linha_botoes = QHBoxLayout()
        linha_botoes.addStretch(1)
        botao_cancelar = _botao_estilizado("Cancelar", cor=TEXT_DIM)
        botao_cancelar.clicked.connect(self.reject)
        linha_botoes.addWidget(botao_cancelar)
        botao_analisar = _botao_estilizado("Analisar")
        botao_analisar.clicked.connect(self._confirmar)
        linha_botoes.addWidget(botao_analisar)
        lay.addLayout(linha_botoes)

    def _confirmar(self):
        self.comentario = self._campo.toPlainText().strip()
        self.accept()


class _DialogoRascunho(QDialog):
    """Mostra o rascunho gerado pra revisar/editar antes de usar (2026-08-15,
    escolha do usuário entre as opções: dialog de revisão em vez de copiar
    direto ou salvar em arquivo) - texto fica editável (o usuário pode
    ajustar antes de copiar), botão "Copiar" joga pra área de transferência."""

    def __init__(self, texto, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rascunho de resposta")
        self.setStyleSheet(f"background-color: {SURFACE_COLOR};")
        self.resize(460, 360)

        lay = QVBoxLayout(self)
        self._texto = QTextEdit()
        self._texto.setPlainText(texto)
        self._texto.setStyleSheet(
            f"background-color: {SURFACE_COLOR}; color: {TEXT_COLOR}; border: 1px solid {BORDA_SUTIL}; border-radius: 6px;"
        )
        lay.addWidget(self._texto, 1)

        linha_botoes = QHBoxLayout()
        linha_botoes.addStretch(1)
        botao_fechar = _botao_estilizado("Fechar", cor=TEXT_DIM)
        botao_fechar.clicked.connect(self.reject)
        linha_botoes.addWidget(botao_fechar)
        botao_copiar = _botao_estilizado("Copiar")
        botao_copiar.clicked.connect(self._copiar)
        linha_botoes.addWidget(botao_copiar)
        lay.addLayout(linha_botoes)

    def _copiar(self):
        QApplication.clipboard().setText(self._texto.toPlainText())


class _PainelDetalhesTicket(QWidget):
    """Janela flutuante própria (2026-08-15, pedido do usuário) com os campos
    detalhados de UM ticket + os botões "Abrir ticket"/"Analisar" - SEPARADA
    da janela principal (diferente da lista de tickets, que é embutida) pra
    não espremer texto longo (Empresa/Plataforma/Tipo de solicitação) na
    coluna estreita da barra."""

    def __init__(self, ao_abrir_ticket, obter_detalhes_completos, analisar_ticket, parent=None):
        super().__init__(parent)
        self._ao_abrir_ticket = ao_abrir_ticket
        self._obter_detalhes_completos = obter_detalhes_completos
        self._analisar_ticket = analisar_ticket
        self._ticket = None
        self._tarefa = None

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(LARGURA_PAINEL_DETALHES)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(6)
        self.setVisible(False)

    def mostrar(self, ticket, x, y):
        self._ticket = ticket
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        linha_topo = QHBoxLayout()
        cor_prioridade = CORES_PRIORIDADE.get(ticket.prioridade, TEXT_COLOR)
        titulo = QLabel(f'<span style="color:{cor_prioridade};">{ticket.chave}</span>')
        titulo.setTextFormat(Qt.RichText)
        titulo.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_NOME, QFont.Bold))
        titulo.setStyleSheet("background: transparent; border: none;")
        linha_topo.addWidget(titulo)
        linha_topo.addStretch(1)
        botao_fechar = QLabel("✕")
        botao_fechar.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        botao_fechar.setCursor(Qt.PointingHandCursor)
        botao_fechar.mousePressEvent = lambda evento: self.esconder()
        linha_topo.addWidget(botao_fechar)
        self._layout.addLayout(linha_topo)

        resumo = QLabel(ticket.resumo)
        resumo.setWordWrap(True)
        resumo.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_DETALHE, QFont.Bold))
        resumo.setStyleSheet(f"color: {TEXT_COLOR}; background: transparent; border: none;")
        self._layout.addWidget(resumo)

        cor_sla = "#f38ba8" if ticket.sla_estourado else TEXT_COLOR
        campos = [
            ("Time to resolution", ticket.sla_texto, cor_sla),
            ("Plataforma", ticket.plataforma, TEXT_COLOR),
            ("Empresa", ticket.empresa, TEXT_COLOR),
            ("Relator", ticket.relator, TEXT_COLOR),
            ("Responsável", ticket.responsavel, TEXT_COLOR),
            ("Tipo de solicitação", ticket.tipo_solicitacao, TEXT_COLOR),
            ("Status", ticket.status, TEXT_COLOR),
        ]
        for rotulo, valor, cor_valor in campos:
            if not valor:
                continue
            self._layout.addWidget(self._linha_campo(rotulo, valor, cor_valor))

        linha_botoes = QHBoxLayout()
        botao_abrir = _botao_estilizado("Abrir ticket")
        botao_abrir.clicked.connect(lambda: self._ao_abrir_ticket(self._ticket))
        linha_botoes.addWidget(botao_abrir)
        # 🔥 "Analisar" precisa das DUAS peças (2026-08-15) - buscar
        # descrição+comentários completos (`obter_detalhes_completos`, do
        # provider) E o gancho de LLM (`analisar_ticket`, injetado por quem
        # sobe o widget) - sem qualquer uma delas, não tem como gerar nada.
        if self._obter_detalhes_completos is not None and self._analisar_ticket is not None:
            self._botao_analisar = _botao_estilizado("Analisar")
            self._botao_analisar.clicked.connect(self._iniciar_analise)
            linha_botoes.addWidget(self._botao_analisar)
        self._layout.addLayout(linha_botoes)

        self.adjustSize()
        self.move(x, y)
        self.setVisible(True)
        self.raise_()

    def esconder(self):
        self.setVisible(False)

    def _linha_campo(self, rotulo, valor, cor_valor) -> QWidget:
        linha = QHBoxLayout()
        linha.setSpacing(6)
        w = QWidget()
        w.setLayout(linha)
        lbl_rotulo = QLabel(f"{rotulo}:")
        lbl_rotulo.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_DETALHE))
        lbl_rotulo.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        linha.addWidget(lbl_rotulo)
        lbl_valor = QLabel(str(valor))
        lbl_valor.setWordWrap(True)
        lbl_valor.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_DETALHE))
        lbl_valor.setStyleSheet(f"color: {cor_valor}; background: transparent; border: none;")
        linha.addWidget(lbl_valor, 1)
        return w

    def _iniciar_analise(self):
        dialogo = _DialogoComentario(self)
        if dialogo.exec() != QDialog.Accepted:
            return
        comentario_extra = dialogo.comentario or ""
        ticket = self._ticket
        self._botao_analisar.setEnabled(False)
        self._botao_analisar.setText("Analisando...")

        def _tarefa():
            detalhes = self._obter_detalhes_completos(ticket.chave)
            return self._analisar_ticket(ticket, detalhes, comentario_extra)

        self._tarefa = _TarefaSegundoPlano(_tarefa, self)
        self._tarefa.concluido.connect(self._analise_concluida)
        self._tarefa.erro.connect(self._analise_falhou)
        self._tarefa.start()

    def _analise_concluida(self, rascunho):
        self._botao_analisar.setEnabled(True)
        self._botao_analisar.setText("Analisar")
        _DialogoRascunho(rascunho, self).exec()

    def _analise_falhou(self, mensagem):
        self._botao_analisar.setEnabled(True)
        self._botao_analisar.setText("Analisar")
        _DialogoRascunho(f"Não consegui analisar: {mensagem}", self).exec()


class ArgusWidget(QWidget):
    def __init__(self, provider, persistencia, analisar_ticket=None):
        super().__init__()
        self._provider = provider
        self._persistencia = persistencia
        self._modo_total = False
        self._categorias = []
        self._chips = []
        self._chave_categoria_aberta = None
        self._fixado = False
        # 🔥 Painel de detalhes (2026-08-15, pedido do usuário) - gancho
        # OPCIONAL de análise (mesmo espírito do `descrever_imagem` do
        # JiraProvider) - o Argus em si não tem LLM nenhuma; quem quiser o
        # botão "Analisar" (ex.: a GAIA, com o Groq dela já configurado)
        # injeta essa função. `getattr` (não `NotificacaoProvider` exigir isso
        # de TODO provider) porque nem todo provider (ex.: `ProviderFalso` dos
        # testes) precisa saber buscar detalhe completo - sem ela, o painel
        # mostra só "Abrir ticket".
        self._painel_detalhes = _PainelDetalhesTicket(
            self._abrir_ticket, getattr(self._provider, "obter_detalhes_completos", None), analisar_ticket, self,
        )

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 🔥 Cantos arredondados nativos do Windows em vez de setMask() manual
        # (2026-08-15, achado pesquisando amnweb/yasb) - winId() força a
        # criação do handle nativo, só depois disso a chamada DWM funciona.
        # Sem suporte (Windows <11, não-Windows, qualquer erro), cai pro
        # mascaramento manual de sempre (ver _atualizar_mascara).
        self.winId()
        self._cantos_nativos_ok = aplicar_cantos_redondos(self)
        remover_cor_borda(self)
        self._mica_ok = ATIVAR_MICA and aplicar_mica(self)
        self._acrylic_ok = (
            not self._mica_ok
            and ATIVAR_ACRYLIC
            and aplicar_acrylic(self, SURFACE_COLOR, ALPHA_ACRYLIC)
        )

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        self._barra = QWidget()
        self._layout_barra = QHBoxLayout(self._barra)
        self._layout_barra.setContentsMargins(12, 8, 12, 8)
        self._layout_barra.setSpacing(6)
        self._alavanca = _Alavanca(self._alternar_modo, self._persistir_posicao, self._barra)
        self._layout_barra.addWidget(self._alavanca)
        layout_raiz.addWidget(self._barra)

        self._painel = _AreaComHover(self._cancelar_fechar, self._agendar_fechar, self)
        self._layout_painel = QVBoxLayout(self._painel)
        self._layout_painel.setContentsMargins(14, 10, 14, 12)
        self._layout_painel.setSpacing(8)
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
        ticket (pra refletir o que foi marcado como visto).

        🔥 Correção (2026-08-15, achado testando: "às vezes a largura diminui
        do nada... foi quando cliquei em um ticket") - `_preencher_painel` mede
        `self._barra.sizeHint()` pra decidir a largura do painel; chamar isso
        LOGO depois de `_reconstruir_barra()` (que acabou de trocar os chips)
        devolvia um valor desatualizado, mesmo problema de fundo do bug de
        encolhimento já corrigido (Qt só recalcula o layout de verdade 1 volta
        do event loop depois). Por isso o reenchimento do painel, quando ele
        já está aberto, é adiado do mesmo jeito."""
        self._categorias = self._provider.listar_categorias()
        self._reconstruir_barra()
        QTimer.singleShot(0, self._atualizar_painel_se_aberto)

    def _atualizar_painel_se_aberto(self):
        if not self._chave_categoria_aberta:
            return
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
        if not self._cantos_nativos_ok:
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

        largura = max(self._barra.sizeHint().width(), 320)

        cabecalho = QLabel(f"{categoria.nome_exibicao} ({categoria.total})")
        cabecalho.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_CABECALHO))
        cabecalho.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        self._layout_painel.addWidget(cabecalho)
        self._layout_painel.addWidget(self._legenda_prioridade())

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
        layout_lista.setSpacing(4)
        layout_lista.setAlignment(Qt.AlignTop)
        for ticket in categoria.tickets:
            layout_lista.addWidget(self._linha_ticket(ticket, largura))
        area.setWidget(conteudo)

        # 🔥 Guarda a referência (self._filtro_roda) - um QObject sem dono
        # Python que ainda referencie é destruído/coletado, e o filtro para
        # de funcionar silenciosamente (ver _RepassaRoda acima). Instala em
        # TODOS os descendentes (não só no container) - varredura recursiva,
        # garante cobertura mesmo se um widget novo for adicionado depois.
        self._filtro_roda = _RepassaRoda(area, self)
        conteudo.installEventFilter(self._filtro_roda)
        for filho in conteudo.findChildren(QWidget):
            filho.installEventFilter(self._filtro_roda)

        self._layout_painel.addWidget(area)

    def _legenda_prioridade(self) -> QWidget:
        """Legenda das cores de prioridade (2026-08-15, pedido do usuário:
        "seria bom também se ficasse claro essas regras de definir prioridade
        em um local visível") - fica junto da própria lista de tickets, onde
        a cor realmente aparece, em vez de escondida num modal de
        configuração separado que o usuário precisaria lembrar de abrir."""
        pedacos = "&nbsp;&nbsp;".join(
            f'<span style="color:{cor};">●</span> {nome}'
            for nome, cor in CORES_PRIORIDADE.items()
        )
        legenda = QLabel(pedacos)
        legenda.setTextFormat(Qt.RichText)
        legenda.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_CABECALHO))
        legenda.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        return legenda

    def _linha_ticket(self, ticket, largura_disponivel) -> QWidget:
        peso = QFont.Bold if ticket.novo else QFont.Normal
        fonte = QFont(FONTE_BASE, TAMANHO_FONTE_TICKET, peso)
        sufixo = " ● NOVO" if ticket.novo else ""
        # 🔥 Pontuação de foco (2026-08-15) à frente da linha - pra ordenar
        # visualmente "o que focar" sem precisar abrir cada ticket (a lista já
        # vem ordenada pelo provider, ver JiraProvider.listar_categorias). Só
        # o resumo elide (o prefixo colorido por prioridade é sempre curto o
        # bastante pra caber inteiro) - a largura medida aqui é em cima do
        # texto PLANO (sem HTML), `_LinhaTicket` que monta o rich text de
        # verdade a partir do ticket.
        prefixo_plano = f"[{ticket.pontuacao_foco}] {ticket.chave}  "
        metricas = QFontMetrics(fonte)
        largura_resumo = max(0, largura_disponivel - 30 - metricas.horizontalAdvance(prefixo_plano))
        resumo_elidido = metricas.elidedText(f"— {ticket.resumo}{sufixo}", Qt.ElideRight, largura_resumo)
        return _LinhaTicket(ticket, resumo_elidido, fonte, self._ticket_clicado)

    def _ticket_clicado(self, ticket):
        """Clicar num ticket agora ABRE O PAINEL DE DETALHES (2026-08-15,
        pedido do usuário) em vez de ir direto pro navegador - abrir o link
        de verdade virou um botão dentro do painel ("Abrir ticket", ver
        `_abrir_ticket`). Posicionado à DIREITA da janela principal (mesma
        borda/topo), fora da coluna estreita da barra de categorias."""
        self._painel_detalhes.mostrar(
            ticket, self.x() + self.width() + ESPACAMENTO_PAINEL_DETALHES, self.y(),
        )

    def _abrir_ticket(self, ticket):
        webbrowser.open(ticket.url)
        self._provider.marcar_visto(ticket.chave)
        self.atualizar()

    # --- janela (pintura/máscara/posição) -------------------------------------

    def paintEvent(self, evento):
        """🔥 Com cantos nativos do DWM (`_cantos_nativos_ok`), o Windows já
        recorta a janela pro formato arredondado - só precisa preencher um
        retângulo normal, sem `QPainterPath`/`setMask` nenhum (2026-08-15,
        achado pesquisando amnweb/yasb - ver win32_dwm.py). Sem suporte, cai
        pro desenho manual de sempre.

        🔥 Acrylic (2026-08-15, testado com 3 níveis e escolhido alpha 120) -
        com Acrylic aplicado de verdade, o preenchimento próprio da janela é
        pulado por completo (só a borda sutil é desenhada) pra deixar o blur
        nativo do Windows aparecer - preencher em cima dele esconderia o
        efeito, mesmo problema que o Mica teve."""
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)

        if self._acrylic_ok:
            if self._cantos_nativos_ok:
                pintor.setPen(QColor(BORDA_SUTIL))
                pintor.drawRect(self.rect().adjusted(0, 0, -1, -1))
            else:
                caminho = QPainterPath()
                caminho.addRoundedRect(self.rect(), RAIO_CANTO, RAIO_CANTO)
                pintor.setPen(QColor(BORDA_SUTIL))
                pintor.drawPath(caminho)
            return

        cor_fundo = QColor(SURFACE_COLOR)
        cor_fundo.setAlpha(ALPHA_FUNDO_COM_MICA if self._mica_ok else ALPHA_FUNDO_SEM_MICA)

        if self._cantos_nativos_ok:
            pintor.fillRect(self.rect(), cor_fundo)
            return

        caminho = QPainterPath()
        caminho.addRoundedRect(self.rect(), RAIO_CANTO, RAIO_CANTO)
        pintor.fillPath(caminho, cor_fundo)
        pintor.setPen(QColor(BORDA_SUTIL))
        pintor.drawPath(caminho)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if not self._cantos_nativos_ok:
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
