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
janela).

🔥 Painel de detalhes ANEXADO/DESTACADO (2026-08-15/16, ver
argus_painel_detalhes_ticket.md) - o painel de detalhes de um ticket nasceu
como janela flutuante própria sempre substituída do zero a cada clique;
depois de uma reescrita com crossfade animado que se mostrou frágil em uso
real (relatado pelo usuário: "tickets se sobrepondo", "não troca quando
seleciono outro"), foi simplificado: clicar num ticket ANEXADO fecha o
painel atual (se houver) e abre um novo do zero, sem animação. Pode ser
DESTACADO (ação do usuário) virando janela independente ARRASTÁVEL (via
pequena barra acima dos botões) presa a um ticket específico, e cada ticket
nunca tem mais de UMA instância aberta (anexada OU destacada, nunca as
duas). Botões/campos seguem o padrão visual da GAIA (`_BotaoIcone`, `Switch`,
`SpinboxCapsula`, ver `_DialogoConfiguracoes`)."""

import os
import webbrowser

from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QPointF, QPoint, QRect, QSize, QEvent, QObject,
    QPropertyAnimation, QEasingCurve, Property,
)
from PySide6.QtGui import (
    QPainter, QPainterPath, QPixmap, QColor, QRegion, QFont, QFontMetrics, QPen, QRadialGradient,
    QGuiApplication, QIntValidator,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QStyleOption, QStyle, QApplication,
    QDialog, QTextEdit, QPlainTextEdit, QPushButton, QLineEdit, QFrame, QCheckBox,
)

from .tema import (
    BG_COLOR, SURFACE_COLOR, HIGHLIGHT_COLOR, BORDA_SUTIL,
    GAIA_GOLD, GAIA_GOLD_HOVER, GAIA_SILVER, TEXT_COLOR, TEXT_DIM, FONTE_BASE, CORES_PRIORIDADE,
    cor_com_alpha,
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
# ticket... botão pra abrir ticket e um pra analisar") - largura fixa
# enquanto ANEXADO, com espaço suficiente pra rótulo+valor sem elidir demais.
LARGURA_PAINEL_DETALHES = 340
ESPACAMENTO_PAINEL_DETALHES = 8
TAMANHO_FONTE_DETALHE = 11

# 🔥 Anexado/Destacado (2026-08-15, ver argus_painel_detalhes_ticket.md) -
# constantes da reescrita do painel de detalhes como extensão visual do
# Argus (em vez de janela flutuante desconectada, sempre recriada do zero).
MARGEM_VERTICAL_TELA_PAINEL_DETALHES = 24
RESERVA_CABECALHO_ACOES_PAINEL_DETALHES = 170
ALTURA_MINIMA_PAINEL_DETALHES = 160
DURACAO_PULSO_ATENCAO_MS = 900
INTERVALO_TIMER_PULSO_ATENCAO_MS = 30
LIMITE_JANELAS_DESTACADAS_PADRAO = 5
# 🔥 Cascata entre janelas destacadas (2026-08-16, correção de bug relatado
# pelo usuário: "os tickets estao se sobrepondo ao selecionar varios" - a
# geometria lembrada era ÚNICA e compartilhada, então destacar 2+ tickets
# seguidos sem arrastar nenhum antes fazia as janelas nascerem exatamente
# empilhadas, indistinguíveis uma da outra) - cada nova janela destacada
# soma este passo × quantas já estão abertas no momento, igual ao "cascade"
# de janela que o próprio Windows faz.
PASSO_CASCATA_JANELAS_DESTACADAS = 32
# 🔥 Chacoalhada de atenção - "pode existir como opção configurável, evitando
# uso frequente" (pedido do usuário) - desligada por padrão; ligável em
# tempo real pelo menu de Configurações (ver `_DialogoConfiguracoes`), este
# valor aqui é só o padrão de fábrica antes de qualquer config salva.
ATIVAR_CHACOALHADA_ATENCAO = False

# 🔥 Glow no chip aberto (2026-08-15) - variante "5c" escolhida: junto com o
# destaque já existente (fundo HIGHLIGHT_COLOR + borda dourada), um brilho
# suave por trás reforça visualmente qual categoria está aberta.
ALPHA_GLOW_ABERTA = 60


def _configurar_janela_flutuante(widget) -> dict:
    """Aplica o mesmo tratamento de janela flutuante (sem borda, transparente,
    cantos nativos + Acrylic/Mica) usado tanto pela janela principal quanto
    pelo painel de detalhes - fatorado (2026-08-15) pra não duplicar a mesma
    sequência de chamadas DWM/flags duas vezes. `winId()` força a criação do
    handle nativo - só depois disso a chamada DWM funciona."""
    widget.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    widget.setAttribute(Qt.WA_TranslucentBackground)
    widget.winId()
    cantos_ok = aplicar_cantos_redondos(widget)
    remover_cor_borda(widget)
    mica_ok = ATIVAR_MICA and aplicar_mica(widget)
    acrylic_ok = not mica_ok and ATIVAR_ACRYLIC and aplicar_acrylic(widget, SURFACE_COLOR, ALPHA_ACRYLIC)
    return {"cantos_ok": cantos_ok, "mica_ok": mica_ok, "acrylic_ok": acrylic_ok}


def _pintar_fundo_janela(widget, pintor, estado: dict):
    """🔥 Com cantos nativos do DWM (`cantos_ok`), o Windows já recorta a
    janela pro formato arredondado - só precisa preencher um retângulo
    normal, sem `QPainterPath`/`setMask` nenhum. Sem suporte, cai pro desenho
    manual de sempre. Com Acrylic aplicado de verdade (`acrylic_ok`), o
    preenchimento próprio é pulado por completo (só a borda sutil é
    desenhada) pra deixar o blur nativo do Windows aparecer."""
    if estado["acrylic_ok"]:
        pintor.setPen(QColor(BORDA_SUTIL))
        if estado["cantos_ok"]:
            pintor.drawRect(widget.rect().adjusted(0, 0, -1, -1))
        else:
            caminho = QPainterPath()
            caminho.addRoundedRect(widget.rect(), RAIO_CANTO, RAIO_CANTO)
            pintor.drawPath(caminho)
        return

    cor_fundo = QColor(SURFACE_COLOR)
    cor_fundo.setAlpha(ALPHA_FUNDO_COM_MICA if estado["mica_ok"] else ALPHA_FUNDO_SEM_MICA)

    if estado["cantos_ok"]:
        pintor.fillRect(widget.rect(), cor_fundo)
        return

    caminho = QPainterPath()
    caminho.addRoundedRect(widget.rect(), RAIO_CANTO, RAIO_CANTO)
    pintor.fillPath(caminho, cor_fundo)
    pintor.setPen(QColor(BORDA_SUTIL))
    pintor.drawPath(caminho)


def _aplicar_mascara_arredondada(widget):
    caminho = QPainterPath()
    caminho.addRoundedRect(widget.rect(), RAIO_CANTO, RAIO_CANTO)
    widget.setMask(QRegion(caminho.toFillPolygon().toPolygon()))


def _limpar_layout(layout):
    """Limpa um `QLayout` RECURSIVAMENTE - inclusive sub-layouts aninhados
    via `addLayout` (2026-08-16, causa raiz real do bug relatado: "quando
    clico no desfixar ele zoa os botões, como acontecia com o redimensionar
    antes de removermos"). `layout.takeAt(0)` devolve um item que pode ser um
    WIDGET direto OU um LAYOUT aninhado - `item.widget()` só devolve algo no
    primeiro caso; sem recursão, widgets DENTRO de um sub-layout (ex.:
    `linha_topo`/`linha_arraste`/`linha_botoes` de
    `_PainelDetalhesTicket.preparar_conteudo`) nunca eram escondidos nem
    destruídos - ficavam órfãos e VISÍVEIS na posição antiga, sobrepostos ao
    conteúdo novo que acabou de ocupar aquele espaço (mesmo bug de fundo já
    corrigido em `_reconstruir_barra`/`_preencher_painel`, que só tinham
    widgets diretos - `preparar_conteudo` é o único lugar com sub-layouts,
    por isso escapou daquela correção)."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.hide()
            widget.deleteLater()
            continue
        sublayout = item.layout()
        if sublayout:
            _limpar_layout(sublayout)


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
        # 🔥 Correção (2026-08-24, mesma pegadinha do Qt já corrigida em
        # `_LinhaTicket` - ver ARQUITETURA.md "Campo INTEIRO clicável de
        # verdade") - sem isso, passar o mouse/clicar em cima da bolinha ou
        # do nome engole o evento antes de chegar no chip, e só o vão vazio
        # (ou a borda) responde de forma confiável.
        bolinha.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(bolinha)

        nome = QLabel(categoria.nome_exibicao)
        nome.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_NOME))
        nome.setStyleSheet(f"color: {TEXT_COLOR}; background: transparent; border: none;")
        nome.setAttribute(Qt.WA_TransparentForMouseEvents)
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
        self._badge.setAttribute(Qt.WA_TransparentForMouseEvents)
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
        # 🔥 `rgba(0, 0, 0, 0.004)` em vez de "transparent" (2026-08-23) -
        # mesma correção de `_LinhaTicket._atualizar_estilo` (ver comentário
        # lá) - alpha zero de verdade vira clique-através pro Windows numa
        # janela translúcida/Acrylic. Só no fundo, não na borda (a borda não
        # precisa do fix, não é onde alguém tenta clicar).
        #
        # 🔥 CORREÇÃO DE UNIDADE (2026-08-23, pedido do usuário: "oq me
        # incomoda é esse preto destoando") - `rgba()` no QSS/CSS usa alpha
        # como FRAÇÃO 0.0-1.0, não um inteiro 0-255 (pegadinha real - o
        # "1" no `rgba(0, 0, 0, 1)` original virou opacidade TOTAL, não
        # "1 de 255"). Resultado: um retângulo preto sólido bem visível atrás
        # de cada cápsula, exatamente o oposto do "imperceptível" pretendido.
        # `0.004` ≈ 1/255 é o valor que eu queria dizer desde o início.
        cor_fundo = HIGHLIGHT_COLOR if aberta else "rgba(0, 0, 0, 0.004)"
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


# 🔥 Cor do TÍTULO por SLA (2026-08-28, pedido do usuário: "faz a cor da
# fonte ser com base na SLA, coloca vermelho p as estouradas, laranja
# faltando 1h, amarelo 2h") - reaproveita os MESMOS tons já usados pra
# prioridade (`CORES_PRIORIDADE`) em vez de inventar uma 2ª paleta de
# vermelho/laranja/amarelo. Só afeta `resumo` (o título) - a cor de
# `prefixo` (chave do ticket) continua exclusivamente pela prioridade,
# decisão anterior mantida (ver comentário logo abaixo, "cor por
# prioridade").
COR_SLA_ESTOURADO = CORES_PRIORIDADE["Highest"]
COR_SLA_LIMIAR_1H = CORES_PRIORIDADE["High"]
COR_SLA_LIMIAR_2H = CORES_PRIORIDADE["Medium"]
LIMIAR_SLA_LARANJA_HORAS = 1
LIMIAR_SLA_AMARELO_HORAS = 2


def _cor_titulo_por_sla(ticket, cor_padrao: str) -> str:
    if ticket.sla_estourado:
        return COR_SLA_ESTOURADO
    millis = ticket.sla_restante_millis
    if millis is None:
        return cor_padrao
    horas_restantes = millis / 3_600_000
    if horas_restantes < LIMIAR_SLA_LARANJA_HORAS:
        return COR_SLA_LIMIAR_1H
    if horas_restantes < LIMIAR_SLA_AMARELO_HORAS:
        return COR_SLA_LIMIAR_2H
    return cor_padrao


def _sufixo_sla(ticket) -> str:
    """Concatenado no final do título - só HORAS inteiras, nunca minutos
    (pedido do usuário: "pode ate concatenar no final do titulo o time to
    resolution, mas apenas horas, ignore minutos"). Formato bem compacto
    (2026-08-28, correção depois do usuário achar a 1ª versão grande demais:
    "n era p ter um sufixo tao grande, apenas (2h) ou (-4h)") - só o número
    entre parênteses, sinal negativo já comunica "estourado há", sem texto
    extra. `int()` trunca em direção a ZERO (não `//`, que arredonda pra
    baixo/mais negativo) - "-4h30m estourado" vira "(-4h)", não "(-5h)"."""
    millis = ticket.sla_restante_millis
    if millis is None:
        return ""
    horas = int(millis / 3_600_000)
    return f" ({horas}h)"


class _LinhaTicket(QWidget):
    """Uma linha de ticket na lista - campo INTEIRO clicável, com destaque
    sutil ao passar o mouse. Clique abre o painel de detalhes (2026-08-15,
    pedido do usuário - ver `ArgusWidget._ticket_clicado`/`_PainelDetalhesTicket`),
    não mais o navegador direto - abrir o link virou um botão dentro do
    painel. Sem ícone/botão separado no final (2026-08-15, pedido do usuário:
    "acho desnecessário esse botão... coloca o efeito dela no próprio campo da
    lista") - hover + cursor de mão já comunicam que a linha inteira é
    clicável, sem precisar de um alvo pequeno separado.

    🔥 Destaque de "aberto" (2026-08-15, ver argus_painel_detalhes_ticket.md,
    "Destacar visualmente na lista o ticket exibido no painel anexado") -
    além do hover (temporário), a linha pode ficar PERSISTENTEMENTE marcada
    (`definir_selecionado`) enquanto o ticket estiver aberto em qualquer
    painel de detalhes (anexado ou destacado) - mesmo tratamento visual do
    hover (fundo + borda dourada), só que não some ao tirar o mouse."""

    def __init__(self, ticket, resumo_elidido, fonte, ao_clicar, parent=None):
        super().__init__(parent)
        self._ticket = ticket
        self._ao_clicar = ao_clicar
        self._hover = False
        self._selecionado = False
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
        pontuacao = QLabel(f"[{ticket.pontuacao_foco}]")
        pontuacao.setObjectName("pontuacao_foco")
        pontuacao.setFont(fonte)
        pontuacao.setStyleSheet(f"color: {cor_texto}; background: transparent; border: none;")
        pontuacao.setToolTip(self._tooltip_pontuacao(ticket))
        layout_linha.addWidget(pontuacao)

        prefixo = QLabel(ticket.chave)
        prefixo.setFont(fonte)
        prefixo.setStyleSheet(f"color: {cor_prioridade}; background: transparent; border: none;")
        # 🔥 Correção (2026-08-21, pedido do usuário: "a seleção no campo tem
        # de ser se o mouse estiver no espaço inteiro, não apenas no texto") -
        # sem isso, um QLabel filho engole o clique (mesma pegadinha real já
        # documentada pro scroll em `_RepassaRoda`/`_ChipCategoria` acima) e
        # `_LinhaTicket.mousePressEvent` só disparava fora do texto (nas
        # margens/vãos entre os dois labels). Transparente pra mouse = o
        # clique atravessa direto pro `_LinhaTicket` por baixo, em QUALQUER
        # ponto da linha.
        prefixo.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout_linha.addWidget(prefixo)

        # 🔥 Cor do título por SLA (2026-08-28) - supera a cor "novo/lido"
        # de sempre (`cor_texto`) quando o SLA estiver estourado ou perto
        # (ver `_cor_titulo_por_sla`); sem SLA aplicável, mantém o
        # comportamento de sempre.
        cor_resumo = _cor_titulo_por_sla(ticket, cor_texto)
        resumo = QLabel(resumo_elidido)
        resumo.setFont(fonte)
        resumo.setStyleSheet(f"color: {cor_resumo}; background: transparent; border: none;")
        resumo.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout_linha.addWidget(resumo, 1)

        self._atualizar_estilo()

    @staticmethod
    def _tooltip_pontuacao(ticket) -> str:
        detalhes = ticket.detalhamento_pontuacao
        if detalhes is None:
            return f"Pontuação de foco: {ticket.pontuacao_foco}"
        rotulo_sla = "SLA estourado" if detalhes.sla_estourado else "SLA restante"
        linhas = [
            f"<b>Pontuação de foco: {detalhes.total}</b>",
            f"Prioridade {detalhes.prioridade}: {detalhes.pontos_prioridade} pontos",
            f"Urgência detectada no texto: +{detalhes.bonus_urgencia}",
            f"{rotulo_sla}: +{detalhes.bonus_sla}",
        ]
        if detalhes.piso_urgencia_aplicado is not None:
            linhas.append(f"Piso por urgência aplicado: {detalhes.piso_urgencia_aplicado}")
        if detalhes.teto_aplicado:
            linhas.append(f"Limite aplicado: {detalhes.limite}")
        return "<br>".join(linhas)

    def definir_selecionado(self, selecionado: bool):
        self._selecionado = selecionado
        self._atualizar_estilo()

    def _atualizar_estilo(self):
        destacar = self._hover or self._selecionado
        # 🔥 Correção (2026-08-23, ver ARQUITETURA.md "Causa raiz real do
        # clique/hover fora do texto") - `background-color: transparent` é
        # alpha ZERO de verdade, e numa janela `WA_TranslucentBackground`/
        # Acrylic como a do Argus, o Windows trata isso como CLIQUE-ATRAVÉS
        # pra quem estiver atrás da janela no desktop - o evento nem chega
        # no Qt. Só o FUNDO precisa do fix (é a área grande onde alguém
        # tenta clicar) - a borda de 1px fica "transparent" de verdade
        # mesmo (um traço fino não precisa disso, e alpha baixo num traço
        # fica mais perceptível do que numa área grande).
        #
        # 🔥 CORREÇÃO DE UNIDADE (2026-08-23, pedido do usuário: "oq me
        # incomoda é esse preto destoando") - `rgba()` no QSS/CSS usa alpha
        # como FRAÇÃO 0.0-1.0, não um inteiro 0-255 (pegadinha real - o "1"
        # em `rgba(0, 0, 0, 1)` virou opacidade TOTAL, não "1 de 255" como
        # pretendido - resultado: um retângulo preto sólido, o oposto do
        # "imperceptível" que era a intenção). `0.004` ≈ 1/255 é o valor
        # certo.
        cor_fundo = HIGHLIGHT_COLOR if destacar else "rgba(0, 0, 0, 0.004)"
        cor_borda = GAIA_GOLD if destacar else "transparent"
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


class _DialogoComentario(QDialog):
    """Pergunta um comentário/instrução opcional ANTES de mandar o ticket pra
    análise (2026-08-15, pedido do usuário: "fazer a análise permitindo
    colocar um comentário") - texto livre, some direto na instrução da LLM
    (ver GAIA, quem injeta `analisar_ticket`), nunca vira comentário de
    verdade no Jira sozinho."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analisar ticket")
        self.setStyleSheet(f"background-color: {BG_COLOR};")
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
        botao_analisar = _botao_estilizado("Analisar", preenchido=True)
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
        self.setStyleSheet(f"background-color: {BG_COLOR};")
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
        botao_copiar = _botao_estilizado("Copiar", preenchido=True)
        botao_copiar.clicked.connect(self._copiar)
        linha_botoes.addWidget(botao_copiar)
        lay.addLayout(linha_botoes)

    def _copiar(self):
        QApplication.clipboard().setText(self._texto.toPlainText())


class _DialogoAvisoLimite(QDialog):
    """Aviso quando o limite de janelas destacadas é atingido (2026-08-15, ver
    argus_painel_detalhes_ticket.md, "Limite de janelas independentes") -
    dialog PRÓPRIO (não QMessageBox nativo, que destoaria visualmente do
    resto do Argus sem borda/translúcido)."""

    def __init__(self, limite, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Limite de janelas atingido")
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self.resize(340, 150)

        lay = QVBoxLayout(self)
        mensagem = QLabel(
            f"Já existem {limite} janela(s) de detalhes destacada(s) - o limite "
            "configurado. Feche ou reanexe uma antes de destacar outra."
        )
        mensagem.setWordWrap(True)
        mensagem.setStyleSheet(f"color: {TEXT_COLOR};")
        lay.addWidget(mensagem, 1)

        linha_botoes = QHBoxLayout()
        linha_botoes.addStretch(1)
        botao_ok = _botao_estilizado("Entendi", preenchido=True)
        botao_ok.clicked.connect(self.accept)
        linha_botoes.addWidget(botao_ok)
        lay.addLayout(linha_botoes)


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


class _DialogoConfiguracoes(QDialog):
    """Menu de configurações do Argus (2026-08-16, pedido do usuário depois
    da reescrita do painel de detalhes - ver
    argus_painel_detalhes_ticket.md) - reúne as opções que antes só davam pra
    mudar editando `.env`/constante no código: limite de janelas destacadas
    e chacoalhada de atenção (efeito opcional, "evitando uso frequente" -
    ficava sem nenhum jeito de ligar sem mexer em código). Persistido via
    `Persistencia.salvar_configuracoes` - aplica em tempo real, sem precisar
    reiniciar o Argus (ver `ArgusWidget.abrir_configuracoes`).

    🔥 Cards no padrão da GAIA (2026-08-16, pedido do usuário: "as
    configuracoes tem varios botoes e campos fora do padrao... os botoes eu
    quero eles no padrao da GAIA. A GAIA vai ser o padrao de todos os
    projetos") - mesmo molde do modal `ModalArgus`
    (assistant/ui/qt_modais/argus.py): `QFrame` com fundo `SURFACE_COLOR` +
    cantos arredondados, título de seção, descrição discreta, e o controle
    (`SpinboxCapsula`/`Switch`) - em vez de um `QFormLayout` cru com
    `QSpinBox`/`QCheckBox` nativos."""

    def __init__(self, limite_atual, chacoalhada_ativa, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações do Argus")
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self.resize(380, 260)
        self.limite_janelas_destacadas = limite_atual
        self.chacoalhada_ativa = chacoalhada_ativa

        lay = QVBoxLayout(self)
        lay.addWidget(self._card_limite(limite_atual))
        lay.addWidget(self._card_chacoalhada(chacoalhada_ativa))
        lay.addStretch(1)

        linha_botoes = QHBoxLayout()
        linha_botoes.addStretch(1)
        botao_cancelar = _botao_estilizado("Cancelar", cor=TEXT_DIM)
        botao_cancelar.clicked.connect(self.reject)
        linha_botoes.addWidget(botao_cancelar)
        botao_salvar = _botao_estilizado("Salvar", preenchido=True)
        botao_salvar.clicked.connect(self._confirmar)
        linha_botoes.addWidget(botao_salvar)
        lay.addLayout(linha_botoes)

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setStyleSheet(f"background-color: {SURFACE_COLOR}; border-radius: 8px;")
        lay_frame = QVBoxLayout(frame)
        return frame, lay_frame

    def _card_limite(self, limite_atual) -> QFrame:
        frame, lay_frame = self._card()
        lay_frame.addWidget(_titulo_secao("Limite de janelas destacadas"))
        lay_frame.addWidget(_descricao(
            "Quantas janelas de detalhes destacadas podem ficar abertas ao "
            "mesmo tempo - ao atingir o limite, o Argus avisa antes de "
            "deixar destacar outra."
        ))
        linha = QHBoxLayout()
        self._campo_limite = SpinboxCapsula(1, 20, limite_atual, largura=90)
        linha.addWidget(self._campo_limite)
        linha.addStretch(1)
        lay_frame.addLayout(linha)
        return frame

    def _card_chacoalhada(self, chacoalhada_ativa) -> QFrame:
        frame, lay_frame = self._card()
        lay_frame.addWidget(_titulo_secao("Chacoalhada de atenção"))
        lay_frame.addWidget(_descricao(
            "Quando você reabre um ticket já destacado, a janela sempre "
            "recebe um pulso na borda/glow - a chacoalhada lateral é um "
            "reforço visual extra, opcional."
        ))
        self._campo_chacoalhada = Switch("Ligada", "Desligada", marcado=chacoalhada_ativa)
        lay_frame.addWidget(self._campo_chacoalhada)
        return frame

    def _confirmar(self):
        self.limite_janelas_destacadas = self._campo_limite.value()
        self.chacoalhada_ativa = self._campo_chacoalhada.isChecked()
        self.accept()


class _AlcaArraste(QWidget):
    """Pequena barra de arraste CENTRALIZADA acima da linha de botões, em
    QUALQUER painel de detalhes - anexado ou destacado (2026-08-16, pedido
    do usuário depois de relatar que arrastar "não está funcionando": "eu só
    quero poder arrastar o ticket... pode criar uma pequena barra
    centralizada no topo que segurando ela e movendo mouse, move o ticket";
    depois ajustado: "pode deixar a barra sempre presente, só que clicar
    nela sem desfixar move tudo" - SEMPRE presente, não só quando destacado,
    e arrasta a janela em qualquer estado sem precisar destacar primeiro).
    Alvo pequeno mas VISÍVEL o tempo todo (antes era uma faixa esticada e
    invisível ocupando o meio do cabeçalho), pra nunca deixar dúvida de onde
    arrastar."""

    LARGURA = 40
    ALTURA = 6

    def __init__(self, painel, parent=None):
        super().__init__(parent)
        self._painel = painel
        self._pos_pressionada = None
        self.setFixedSize(self.LARGURA, self.ALTURA)
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip("Arrastar")

    def mousePressEvent(self, evento):
        self._pos_pressionada = evento.globalPosition().toPoint()

    def mouseMoveEvent(self, evento):
        if self._pos_pressionada is None:
            return
        atual = evento.globalPosition().toPoint()
        delta = atual - self._pos_pressionada
        if self._painel.destacado:
            janela = self._painel.window()
            janela.move(janela.pos() + delta)
        else:
            # 🔥 Anexado = "vinculado à barra de status" (2026-08-16, pedido
            # do usuário: "tem q mover TUDO, a barra dos status tbm") - move
            # a janela PRINCIPAL em vez deste painel; o painel já segue ela
            # sozinho (`ArgusWidget.moveEvent`), então os dois andam juntos.
            self._painel.mover_vinculado(delta)
        self._pos_pressionada = atual

    def mouseReleaseEvent(self, evento):
        self._pos_pressionada = None

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        pintor.setPen(Qt.NoPen)
        pintor.setBrush(QColor(TEXT_DIM))
        pintor.drawRoundedRect(self.rect(), self.ALTURA / 2, self.ALTURA / 2)


TAMANHO_BOTAO_ICONE = 28


class _BotaoIcone(QPushButton):
    """Botão de ícone (emoji) no PADRÃO VISUAL DA GAIA (2026-08-16, pedido do
    usuário: "os botões eu quero eles no padrão da GAIA. A GAIA vai ser o
    padrão de todos os projetos") - mesmo molde de `criar_botao_pequeno`
    (assistant/ui/qt_widgets.py, copiado aqui, não importado - ver docstring
    do módulo): fundo/borda SEMPRE visíveis (nunca só no hover), hover mais
    forte. `QPushButton` NATIVO em vez do QLabel usado antes - o Qt já
    garante clique correto em QUALQUER ponto do botão de graça, sem precisar
    calcular hit-area na mão (resolve de vez o relatado "parece que tem que
    clicar na posição exata do texto/ícone").

    `riscado` (opcional) desenha uma linha diagonal por cima do ícone - usado
    pelo alfinete de Destacar/Reanexar ("alfinete riscado e normal") em vez
    de um segundo emoji (nenhum emoji de "despinar" rende de forma confiável
    em toda fonte/SO - desenhar a linha na mão garante o mesmo resultado
    sempre)."""

    def __init__(self, texto, tooltip, ao_clicar, cor=TEXT_DIM, tamanho_fonte=13, riscado=False, parent=None):
        super().__init__(texto, parent)
        self._cor = cor
        self._riscado = riscado
        self.setFixedSize(TAMANHO_BOTAO_ICONE, TAMANHO_BOTAO_ICONE)
        self.setFont(QFont(FONTE_BASE, tamanho_fonte))
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self.clicked.connect(ao_clicar)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {HIGHLIGHT_COLOR}; color: {self._cor};
                border: 1px solid {BORDA_SUTIL}; border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: {BORDA_SUTIL}; }}
        """)

    def definir_riscado(self, riscado: bool, tooltip: str = None):
        self._riscado = riscado
        if tooltip is not None:
            self.setToolTip(tooltip)
        self.update()

    def paintEvent(self, evento):
        super().paintEvent(evento)
        if self._riscado:
            # 🔥 Diagonal INVERTIDA (2026-08-16, pedido do usuário: "inverte
            # o bloqueio no alfinete, ta se sobrepondo e mal da p ver" - a
            # diagonal "/" (de baixo-esquerda a cima-direita) cruzava bem em
            # cima do corpo do alfinete, ficando confuso/pouco legível.
            # "\" (de cima-esquerda a baixo-direita) cruza menos o glifo.
            pintor = QPainter(self)
            pintor.setRenderHint(QPainter.Antialiasing)
            pintor.setPen(QPen(QColor("#e05d5d"), 2))
            margem = 6
            pintor.drawLine(margem, margem, self.width() - margem, self.height() - margem)


class _RotuloClicavel(QLabel):
    """QLabel clicável com hit-area PRÓPRIA e SEMPRE visível (2026-08-16,
    mesmo pedido do usuário que motivou `_BotaoIcone` acima) - usado no
    código do ticket (clique pra copiar), que precisa de texto rico (cor por
    prioridade) em vez de um emoji fixo, então não reaproveita `_BotaoIcone`
    direto. Override de CLASSE do `mousePressEvent` (nunca
    `label.mousePressEvent = lambda...` por instância) + padding reservado
    via QSS, pra nunca depender de acertar o texto no pixel exato."""

    def __init__(self, texto, tooltip, ao_clicar, parent=None):
        super().__init__(texto, parent)
        self._ao_clicar = ao_clicar
        self._hover = False
        self.setTextFormat(Qt.RichText)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self._atualizar_estilo()

    def _atualizar_estilo(self):
        cor_fundo = HIGHLIGHT_COLOR if self._hover else "transparent"
        self.setStyleSheet(
            f"background-color: {cor_fundo}; border: none; border-radius: 6px; padding: 3px 4px;"
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
        self._ao_clicar()


class _PainelDetalhesTicket(QWidget):
    """Painel de detalhes de UM ticket (2026-08-15, ver
    argus_painel_detalhes_ticket.md). Por padrão fica ANEXADO - segue a
    janela principal. Pode ser DESTACADO via ação "Destacar", virando janela
    independente (arrastável/redimensionável) presa a ESTE ticket até ser
    reanexada ou fechada.

    🔥 Simplificado (2026-08-16, pedido do usuário depois de bugs reais em
    uso: "ainda esta tendo problema de tickets se sobrepondo, e n trocando
    qnd seleciono outro... é p ser simples, clicou no ticket apareceu ele do
    lado, clicou em outro ticket, some o anterior e abre o novo") - a versão
    anterior reaproveitava UMA instância com crossfade animado entre
    tickets; isso se mostrou frágil em uso real (só validado por chamada
    síncrona em teste automatizado, nunca pela animação de verdade rodando
    no loop de eventos real). Removido o crossfade/reaproveitamento: cada
    ticket clicado no painel anexado FECHA a instância atual (se houver) e
    ABRE uma instância nova do zero (`ArgusWidget._ticket_clicado`) - sem
    animação de entrada nem de troca, mostra na posição final direto.

    Terminologia: "anexado" = painel conectado à janela principal;
    "destacar"/"destacado" = virar janela independente; "reanexar" = devolver
    ao painel principal. Todas as instâncias são top-level SEM parent Qt
    (mesmo enquanto anexadas) - o ArgusWidget controla o ciclo de vida
    explicitamente (ver `ArgusWidget.closeEvent`), em vez de depender do Qt
    destruir filhos junto com o pai (isso quebraria a regra de que janelas
    destacadas sobrevivem ao fechamento da janela principal)."""

    def __init__(
        self, ao_abrir_ticket, obter_detalhes_completos, analisar_ticket,
        ao_atualizar, ao_alternar_destaque, ao_fechar, obter_chacoalhada_ativa=None,
        ao_mover_vinculado=None,
    ):
        super().__init__(None)
        self._ao_abrir_ticket = ao_abrir_ticket
        self._obter_detalhes_completos = obter_detalhes_completos
        self._analisar_ticket = analisar_ticket
        self._ao_atualizar = ao_atualizar
        self._ao_alternar_destaque = ao_alternar_destaque
        self._ao_fechar = ao_fechar
        # 🔥 Arraste VINCULADO (2026-08-16, pedido do usuário: "a barra de
        # arraste, qnd estiver vinculada a barra dos status, tem q mover
        # TUDO, a barra dos status tbm") - enquanto ANEXADO, arrastar move a
        # janela PRINCIPAL (não este painel) - o painel já segue ela sozinho
        # (`ArgusWidget.moveEvent`), então mover a principal move os dois
        # juntos, como um bloco só. Só usado em modo anexado (ver
        # `_AlcaArraste.mouseMoveEvent`) - destacado continua movendo só a si
        # mesmo, por ser independente.
        self._ao_mover_vinculado = ao_mover_vinculado
        # 🔥 Configurável em tempo real via menu de Configurações (2026-08-16,
        # ver `_DialogoConfiguracoes`/`ArgusWidget.abrir_configuracoes`) - um
        # CALLABLE (não um bool capturado na criação) pra ligar/desligar
        # refletir imediatamente em painéis já abertos, sem precisar recriá-
        # los. Sem injeção (ex.: uso fora do ArgusWidget), cai pro padrão
        # desligado do módulo.
        self._obter_chacoalhada_ativa = obter_chacoalhada_ativa or (lambda: ATIVAR_CHACOALHADA_ATENCAO)

        self._ticket = None
        self._tarefa = None
        self.destacado = False
        self._lado = "direita"
        self._fase_pulso = 1.0
        self._timer_pulso = None

        self._estado_janela = _configurar_janela_flutuante(self)
        self.setFixedWidth(LARGURA_PAINEL_DETALHES)

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        self._conteudo_raiz = QWidget(self)
        self._conteudo_raiz.setStyleSheet("background: transparent;")
        layout_raiz.addWidget(self._conteudo_raiz)
        self._layout = QVBoxLayout(self._conteudo_raiz)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(6)

        self.setVisible(False)

    # --- consulta de estado ---------------------------------------------

    def ticket_atual_chave(self):
        return self._ticket.chave if self._ticket else None

    # --- abertura/troca (modo anexado) ------------------------------------

    def preparar_conteudo(self, ticket):
        """Reconstrói os campos exibidos pra este ticket - chamado antes da
        primeira exibição e no meio do crossfade (com o conteúdo já
        invisível), nunca recria a JANELA em si."""
        self._ticket = ticket
        # 🔥 Limpeza RECURSIVA (2026-08-16, causa raiz real do bug relatado:
        # "quando clico no desfixar ele zoa os botões, como acontecia com o
        # redimensionar antes de removermos") - ver `_limpar_layout`: este
        # `self._layout` tem SUB-layouts aninhados (linha_arraste/linha_topo/
        # linha_botoes), e uma limpeza só de nível 1 nunca escondia os
        # widgets DENTRO deles, que ficavam órfãos e visíveis por cima do
        # conteúdo novo (título/botões duplicados na tela).
        _limpar_layout(self._layout)

        # 🔥 Barra de arraste SEMPRE presente (2026-08-16, pedido do usuário:
        # "pode deixar a barra sempre presente, só que clicar nela sem
        # desfixar move tudo") - antes só existia em modo destacado; agora
        # arrasta a janela (anexada ou destacada) em qualquer estado, sem
        # precisar destacar primeiro.
        linha_arraste = QHBoxLayout()
        linha_arraste.addStretch(1)
        linha_arraste.addWidget(_AlcaArraste(self))
        linha_arraste.addStretch(1)
        self._layout.addLayout(linha_arraste)

        linha_topo = QHBoxLayout()
        cor_prioridade = CORES_PRIORIDADE.get(ticket.prioridade, TEXT_COLOR)
        titulo = _RotuloClicavel(
            f'<span style="color:{cor_prioridade};">{ticket.chave}</span>',
            "Clique para copiar o código do ticket", self._copiar_codigo,
        )
        titulo.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_NOME, QFont.Bold))
        linha_topo.addWidget(titulo)
        # 🔥 Ícones no cabeçalho (2026-08-16, ajuste de posição pedido pelo
        # usuário) - 🔗 Copiar link cola no ticket, à ESQUERDA (ao lado do
        # código); o alfinete (Destacar/Reanexar) fica ao lado do ⟳
        # Atualizar, à direita, junto do ✕ - substituem os antigos botões de
        # texto "Copiar link"/"Atualizar"/"Destacar"/"Reanexar" da linha de
        # ações debaixo.
        botao_copiar_link = _BotaoIcone("🔗", "Copiar link", self._copiar_link)
        linha_topo.addWidget(botao_copiar_link)
        linha_topo.addStretch(1)
        tooltip_alfinete = "Reanexar" if self.destacado else "Destacar"
        self._botao_alfinete = _BotaoIcone(
            "📌", tooltip_alfinete, lambda: self._ao_alternar_destaque(self), riscado=self.destacado,
        )
        linha_topo.addWidget(self._botao_alfinete)
        botao_atualizar = _BotaoIcone("⟳", "Atualizar", lambda: self._ao_atualizar(), tamanho_fonte=16)
        linha_topo.addWidget(botao_atualizar)
        botao_fechar = _BotaoIcone("✕", "Fechar", lambda: self._ao_fechar(self))
        linha_topo.addWidget(botao_fechar)
        self._layout.addLayout(linha_topo)

        resumo = QLabel(ticket.resumo)
        resumo.setWordWrap(True)
        resumo.setFont(QFont(FONTE_BASE, TAMANHO_FONTE_DETALHE, QFont.Bold))
        resumo.setStyleSheet(f"color: {TEXT_COLOR}; background: transparent; border: none;")
        self._layout.addWidget(resumo)

        conteudo_campos = QWidget()
        conteudo_campos.setStyleSheet("background: transparent;")
        layout_campos = QVBoxLayout(conteudo_campos)
        layout_campos.setContentsMargins(0, 0, 0, 0)
        layout_campos.setSpacing(6)
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
            layout_campos.addWidget(self._linha_campo(rotulo, valor, cor_valor))

        # 🔥 Rolagem interna só quando o conteúdo passa do limite da área
        # útil do monitor (2026-08-15, ver argus_painel_detalhes_ticket.md,
        # "Tamanho e conteúdo") - mesmo padrão já usado pra lista de tickets
        # (`ArgusWidget._preencher_painel`): só existe QScrollArea quando
        # REALMENTE precisa, senão a altura natural encolhe/cresce sem o bug
        # de "não encolhe mais" que um QScrollArea sempre presente causaria.
        altura_max_conteudo = self._altura_maxima_disponivel() - RESERVA_CABECALHO_ACOES_PAINEL_DETALHES
        if conteudo_campos.sizeHint().height() > altura_max_conteudo:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QScrollArea.NoFrame)
            area.setStyleSheet("background: transparent; border: none;")
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setFixedHeight(max(int(altura_max_conteudo), ALTURA_MINIMA_PAINEL_DETALHES // 2))
            area.setWidget(conteudo_campos)
            self._layout.addWidget(area)
        else:
            self._layout.addWidget(conteudo_campos)

        self._layout.addLayout(self._montar_linha_acoes())

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

    def _montar_linha_acoes(self) -> QHBoxLayout:
        # 🔥 Botões enxutos (2026-08-16, pedido do usuário) - "Abrir no Jira"
        # virou só "Abrir"; Copiar link/Atualizar/Destacar/Reanexar saíram
        # daqui, viraram ícones no cabeçalho (ver `preparar_conteudo`).
        linha_botoes = QHBoxLayout()
        botao_abrir = _botao_estilizado("Abrir")
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

        linha_botoes.addStretch(1)
        return linha_botoes

    def _altura_maxima_disponivel(self) -> float:
        tela = self.screen() or QGuiApplication.primaryScreen()
        area = tela.availableGeometry()
        return max(200, area.height() - 2 * MARGEM_VERTICAL_TELA_PAINEL_DETALHES)

    def mostrar(self, x, y, largura, altura, lado):
        """Mostra o painel na posição final - conteúdo já deve ter sido
        preparado (`preparar_conteudo`) por quem chama. Sem animação de
        entrada (2026-08-16, simplificação pedida pelo usuário - ver
        docstring da classe): aparece direto, sem gerar oportunidade pra
        janela antiga e a nova coexistirem visualmente por qualquer tempo."""
        self._lado = lado
        self.setGeometry(x, y, largura, altura)
        self.setVisible(True)
        self.raise_()

    def atualizar_se_mostrando(self, ticket):
        """Chamado a cada polling (`ArgusWidget.atualizar`) - se este painel
        estiver mostrando o MESMO ticket, atualiza os campos (prioridade/
        status/SLA/comentário) sem recriar a janela, só o conteúdo interno
        (2026-08-15, ver argus_painel_detalhes_ticket.md, "Tamanho e
        conteúdo")."""
        if not self._ticket or self._ticket.chave != ticket.chave or not self.isVisible():
            return
        self.preparar_conteudo(ticket)
        if not self.destacado:
            self.resize(self.width(), min(self.sizeHint().height(), int(self._altura_maxima_disponivel())))

    def reposicionar(self, x, y, lado):
        """Segue a janela principal quando ela se move (ver
        `ArgusWidget.moveEvent`) - só em modo anexado; recalcula o lado se o
        Argus mudou de monitor."""
        self._lado = lado
        self.move(x, y)
        self.update()

    def mover_vinculado(self, delta):
        """Arraste da barra em modo ANEXADO (ver `_AlcaArraste`) - move a
        janela PRINCIPAL em vez desta (que já segue ela sozinha), pra
        arrastar os dois juntos como um bloco só."""
        if self._ao_mover_vinculado:
            self._ao_mover_vinculado(delta)

    def esconder(self):
        self.setVisible(False)
        self._ticket = None

    # --- destacar/reanexar ---------------------------------------------------

    def tornar_destacado(self, x, y, largura, altura):
        """Vira janela independente ARRASTÁVEL (2026-08-16, pedido do
        usuário: "eu só quero poder arrastar o ticket") - sem redimensionar
        (o botão de redimensionar foi removido: "usar ele esta duplicando
        botoes"), então o tamanho fica fixo no valor calculado na hora de
        destacar."""
        self.destacado = True
        self.setGeometry(x, y, largura, altura)
        self.preparar_conteudo(self._ticket)

    def fechar_definitivo(self):
        if self._timer_pulso:
            self._timer_pulso.stop()
        self.setVisible(False)
        self.deleteLater()

    # --- atenção (janela destacada já aberta) --------------------------------

    def trazer_para_frente_com_atencao(self):
        self.raise_()
        self.activateWindow()
        self._disparar_pulso_atencao()
        if self._obter_chacoalhada_ativa():
            self._chacoalhar()

    def _disparar_pulso_atencao(self):
        self._fase_pulso = 0.0
        if self._timer_pulso is None:
            self._timer_pulso = QTimer(self)
            self._timer_pulso.timeout.connect(self._avancar_pulso)
        self._timer_pulso.start(INTERVALO_TIMER_PULSO_ATENCAO_MS)

    def _avancar_pulso(self):
        self._fase_pulso += INTERVALO_TIMER_PULSO_ATENCAO_MS / DURACAO_PULSO_ATENCAO_MS
        if self._fase_pulso >= 1.0:
            self._fase_pulso = 1.0
            self._timer_pulso.stop()
        self.update()

    def _chacoalhar(self):
        """Efeito opcional (desligado por padrão, liga/desliga no menu de
        Configurações - ver `_DialogoConfiguracoes`) - pequeno deslocamento
        lateral de ida e volta, "evitando uso frequente" (pedido do usuário)."""
        pos_original = self.pos()
        sequencia = [8, -8, 5, -5, 0]

        def _passo(indice=0):
            if indice >= len(sequencia):
                return
            self.move(pos_original.x() + sequencia[indice], pos_original.y())
            QTimer.singleShot(35, lambda: _passo(indice + 1))

        _passo()

    # --- ações rápidas ---------------------------------------------------

    def _copiar_codigo(self):
        if self._ticket:
            QApplication.clipboard().setText(self._ticket.chave)

    def _copiar_link(self):
        if self._ticket:
            QApplication.clipboard().setText(self._ticket.url)

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

    # --- janela (pintura/máscara) --------------------------------------------

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        _pintar_fundo_janela(self, pintor, self._estado_janela)

        if not self.destacado:
            self._pintar_conector(pintor)

        if self._fase_pulso < 1.0:
            alpha = int(200 * (1.0 - self._fase_pulso))
            cor = QColor(GAIA_GOLD)
            cor.setAlpha(alpha)
            caminho = QPainterPath()
            caminho.addRoundedRect(self.rect().adjusted(1, 1, -2, -2), RAIO_CANTO, RAIO_CANTO)
            pintor.setPen(QPen(cor, 3))
            pintor.drawPath(caminho)

    def _pintar_conector(self, pintor):
        """Continuidade visual com a janela principal (2026-08-15, ver
        argus_painel_detalhes_ticket.md, "Manter continuidade visual... por
        meio do alinhamento, glow ou pequeno indicador de conexão") - uma
        faixa dourada sutil na borda do painel voltada pra janela principal,
        só enquanto ANEXADO."""
        cor = QColor(GAIA_GOLD)
        cor.setAlpha(ALPHA_GLOW_ABERTA + 40)
        largura_faixa = 3
        if self._lado == "direita":
            pintor.fillRect(0, 0, largura_faixa, self.height(), cor)
        else:
            pintor.fillRect(self.width() - largura_faixa, 0, largura_faixa, self.height(), cor)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if not self._estado_janela["cantos_ok"]:
            _aplicar_mascara_arredondada(self)


class ArgusWidget(QWidget):
    def __init__(
        self, provider, persistencia, analisar_ticket=None,
        limite_janelas_destacadas=LIMITE_JANELAS_DESTACADAS_PADRAO,
    ):
        super().__init__()
        self._provider = provider
        self._persistencia = persistencia
        self._analisar_ticket_gancho = analisar_ticket
        self._modo_total = False
        self._categorias = []
        self._chips = []
        self._chave_categoria_aberta = None
        self._fixado = False
        # 🔥 Busca em thread própria (2026-08-23, ver docstring de `atualizar()`
        # pro motivo) - guarda a referência pra não deixar o QThread ser
        # coletado pelo GC no meio da execução, e pra `atualizar()` saber se
        # já tem uma busca em andamento.
        self._tarefa_atualizacao = None

        # 🔥 Painel de detalhes anexado/destacado (2026-08-15, ver
        # argus_painel_detalhes_ticket.md) - `_painel_anexado` é a instância
        # ÚNICA reaproveitada (crossfade) enquanto anexada; ao destacar, ela
        # PRÓPRIA vira a janela independente (registrada em
        # `_janelas_destacadas`) e uma instância nova/vazia assume o slot
        # anexado - nunca duas instâncias pro mesmo ticket (ver
        # `_ticket_clicado`).
        self._janelas_destacadas = {}
        # 🔥 Menu de Configurações (2026-08-16, ver `_DialogoConfiguracoes`) -
        # config PERSISTIDA tem prioridade sobre o argumento do construtor
        # (esse já vem do `.env` no uso standalone, ver app.py) - se o
        # usuário já mudou algo pelo menu antes, isso prevalece entre
        # reinícios.
        config_salva = persistencia.obter_configuracoes()
        self._limite_janelas_destacadas = config_salva.get("limite_janelas_destacadas", limite_janelas_destacadas)
        self._chacoalhada_ativa = config_salva.get("chacoalhada_ativa", ATIVAR_CHACOALHADA_ATENCAO)
        self._painel_anexado = self._criar_painel_detalhes()

        estado_janela = _configurar_janela_flutuante(self)
        self._estado_janela = estado_janela

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
        já está aberto, é adiado do mesmo jeito.

        🔥 Correção (2026-08-23, reportado pelo usuário: "Não consegui abrir o
        Argus: HTTPSConnectionPool... Connection timed out" tentando abrir
        pela GAIA) - uma falha de rede/timeout ao consultar o Jira (comum,
        transitória - servidor lento, Wi-Fi instável, VPN etc.) subia sem
        tratamento daqui, e como esta função também roda dentro do
        `__init__` (primeira carga), a criação do `ArgusWidget` INTEIRA
        falhava - o widget nem chegava a abrir. `atualizar()` também é
        chamada pelo QTimer de polling a cada N minutos, então sem essa
        proteção o MESMO tipo de falha quebraria silenciosamente o
        monitoramento depois de aberto, não só na abertura. Uma falha aqui
        só loga e mantém a última lista de categorias que já tinha (vazia,
        na abertura) - tenta de novo sozinho no próximo ciclo do QTimer, sem
        exigir reabrir o Argus.

        🔥 Busca em thread própria (2026-08-23, reportado pelo usuário: "pq
        demora p abrir o argus pela gaia") - `self._provider.listar_categorias()`
        faz VÁRIAS chamadas de rede sequenciais (JQL x4 + SLA/changelog/issue
        vinculado por ticket), e essa função rodava direto na THREAD DA UI -
        como `atualizar()` roda dentro do próprio `__init__`, abrir o Argus
        pela GAIA travava a janela PRINCIPAL inteira (Painel, bandeja, tudo)
        até a busca inteira terminar, minutos em alguns casos com a rede
        instável observada nesta mesma sessão. Agora a busca roda numa
        `_TarefaSegundoPlano` (mesmo QThread já usado pelo botão "Analisar")
        - o widget abre e a janela principal da GAIA continua responsiva na
        hora, os dados chegam e populam a barra assim que a busca terminar
        (`_ao_atualizar_concluido`/`_ao_atualizar_falhou`, sempre na thread da
        UI via Signal, nunca mexendo em widget Qt de dentro da thread de
        fundo). Se uma busca anterior ainda estiver rodando quando o próximo
        ciclo do QTimer disparar, este `atualizar()` simplesmente não
        empilha outra - espera a atual terminar."""
        if self._tarefa_atualizacao is not None and self._tarefa_atualizacao.isRunning():
            return
        self._tarefa_atualizacao = _TarefaSegundoPlano(self._provider.listar_categorias, self)
        self._tarefa_atualizacao.concluido.connect(self._ao_atualizar_concluido)
        self._tarefa_atualizacao.erro.connect(self._ao_atualizar_falhou)
        self._tarefa_atualizacao.start()

    def _ao_atualizar_concluido(self, categorias):
        self._categorias = categorias
        self._reconstruir_barra()
        QTimer.singleShot(0, self._atualizar_painel_se_aberto)
        self._atualizar_paineis_de_detalhes_abertos()

    def _ao_atualizar_falhou(self, mensagem):
        print(f"[Argus] Falha ao buscar dados do Jira (tentando de novo no próximo ciclo): {mensagem}")

    def _atualizar_paineis_de_detalhes_abertos(self):
        """Se prioridade/status/SLA/comentários mudarem num ticket que já
        está com o painel aberto (anexado ou destacado), atualiza os dados
        SEM recriar nada (ver `_PainelDetalhesTicket.atualizar_se_mostrando`)."""
        por_chave = {t.chave: t for c in self._categorias for t in c.tickets}
        chave_anexado = self._painel_anexado.ticket_atual_chave()
        if chave_anexado and chave_anexado in por_chave:
            self._painel_anexado.atualizar_se_mostrando(por_chave[chave_anexado])
        for chave, painel in self._janelas_destacadas.items():
            if chave in por_chave:
                painel.atualizar_se_mostrando(por_chave[chave])

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
            # 🔥 `hide()` antes do `deleteLater()` (2026-08-16, mesma correção
            # de `_preencher_painel` abaixo) - `removeWidget` não esconde o
            # widget, só para de gerenciar a geometria dele.
            chip.hide()
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
        if not self._estado_janela["cantos_ok"]:
            _aplicar_mascara_arredondada(self)

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
                # 🔥 Correção (2026-08-16, bug relatado: "os tickets estao se
                # sobrepondo ao selecionar varios") - `deleteLater()` sozinho
                # só destrói o widget numa volta futura do loop de eventos;
                # até lá ele continua VISÍVEL na última posição (`takeAt` só
                # para de gerenciar a geometria, não esconde) - sobreposto às
                # linhas novas que acabaram de ocupar o mesmo espaço.
                # `hide()` remove da tela na hora, síncrono.
                widget.hide()
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
        # 🔥 Sufixo de SLA (2026-08-28) - entra na MESMA string que já elide
        # (como o "● NOVO" de sempre), então some primeiro se a linha for
        # curta demais pra caber tudo - mesma prioridade visual do resto.
        resumo_elidido = metricas.elidedText(f"— {ticket.resumo}{sufixo}{_sufixo_sla(ticket)}", Qt.ElideRight, largura_resumo)
        linha = _LinhaTicket(ticket, resumo_elidido, fonte, self._ticket_clicado)
        linha.definir_selecionado(self._ticket_esta_aberto(ticket.chave))
        return linha

    def _ticket_esta_aberto(self, chave) -> bool:
        return self._painel_anexado.ticket_atual_chave() == chave or chave in self._janelas_destacadas

    # --- painel de detalhes: anexado/destacado/instâncias --------------------

    def _criar_painel_detalhes(self) -> _PainelDetalhesTicket:
        return _PainelDetalhesTicket(
            self._abrir_ticket,
            getattr(self._provider, "obter_detalhes_completos", None),
            self._analisar_ticket_gancho,
            self.atualizar,
            self._alternar_destaque,
            self._fechar_painel_detalhes,
            obter_chacoalhada_ativa=lambda: self._chacoalhada_ativa,
            ao_mover_vinculado=self._mover_vinculado_ao_painel,
        )

    def _mover_vinculado_ao_painel(self, delta):
        """Arraste da barra do painel ANEXADO (2026-08-16, pedido do
        usuário: "a barra de arraste, qnd estiver vinculada a barra dos
        status, tem q mover TUDO, a barra dos status tbm") - move a janela
        PRINCIPAL; o painel anexado já segue ela sozinho (`moveEvent`
        abaixo), então os dois se movem juntos como um bloco só."""
        self.move(self.pos() + delta)

    # --- menu de configurações -----------------------------------------------

    def abrir_configuracoes(self):
        """Ponto de entrada público (2026-08-16, ver
        argus_painel_detalhes_ticket.md) - chamado pelo menu da bandeja no
        uso standalone (ver app.py); rodando embutido na GAIA, quem
        instanciar o `ArgusWidget` pode ligar isso na própria UI (ex.: um
        item de menu no Painel dela) do mesmo jeito."""
        dialogo = _DialogoConfiguracoes(self._limite_janelas_destacadas, self._chacoalhada_ativa, self)
        if dialogo.exec() == QDialog.Accepted:
            self._limite_janelas_destacadas = dialogo.limite_janelas_destacadas
            self._chacoalhada_ativa = dialogo.chacoalhada_ativa
            self._persistencia.salvar_configuracoes({
                "limite_janelas_destacadas": self._limite_janelas_destacadas,
                "chacoalhada_ativa": self._chacoalhada_ativa,
            })

    def _ticket_clicado(self, ticket):
        """Controle de instância (2026-08-15, ver
        argus_painel_detalhes_ticket.md, "Controle de instâncias") - nunca
        cria uma segunda janela pro mesmo ticket:
        1. já destacado -> traz a janela pra frente + efeito de atenção.
        2. já no painel anexado -> mantém e atualiza os dados.
        3. nenhum dos dois -> fecha o painel anexado atual (se houver algum
           ticket nele) e abre um painel NOVO do zero pro ticket clicado.

        🔥 Simplificado (2026-08-16, bug relatado pelo usuário mesmo depois
        de uma tentativa anterior de correção: "ainda esta tendo problema de
        tickets se sobrepondo, e n trocando qnd seleciono outro... é p ser
        simples, clicou no ticket apareceu ele do lado, clicou em outro
        ticket, some o anterior e abre o novo") - a versão anterior
        reaproveitava a mesma instância com crossfade animado; removido
        (ver `_PainelDetalhesTicket`) porque só foi validado por chamada
        síncrona em teste automatizado, nunca pela animação de verdade no
        loop de eventos real - fechar e recriar do zero é mais simples e
        elimina essa classe inteira de bug de sincronismo.

        🔥 Correção (2026-08-16, bug relatado pelo usuário com print de tela:
        "se eu desfixo um ticket, clico em outro, e volto nesse q esta
        desfixado, não é para ter nenhum fixado... assim que clico em um
        ticket, apenas o selecionado tem de aparecer") - trazer uma janela
        DESTACADA pra frente também fecha o painel ANEXADO (se estiver
        mostrando outro ticket), que senão continuava aberto/destacado na
        lista junto com a janela destacada - dois tickets pareciam
        "selecionados" ao mesmo tempo. Outras janelas destacadas (de
        OUTROS tickets) continuam existindo - só o slot anexado (a "seleção
        implícita" de quem não foi destacado de propósito) é fechado.

        🔥 Toggle (2026-08-21, pedido do usuário: "em vez de só sair quando
        clicar em abrir, tira quando clico no campo") - clicar de novo no
        MESMO ticket já aberto no painel anexado agora FECHA o painel (só
        pra esse caso; um ticket já destacado continua só trazendo a janela
        pra frente, ver acima). Antes só saía marcando visto ao clicar
        "Abrir" (link do Jira) ou trocando de ticket - clicar no campo pra
        fechar o que já estava aberto não fazia nada.

        🔥 Marca visto AQUI (2026-08-21, mesmo pedido) - abrir o ticket no
        painel (o "campo" da lista) já limpa a novidade dele, sem precisar
        clicar em "Abrir" no Jira pra isso (ver ARQUITETURA.md, "regra de
        novidade": "só abrir o ticket individual... limpa a novidade").
        Muda só o objeto Ticket em memória (`self._categorias` guarda a
        MESMA referência) + reconstrói a barra - sem `atualizar()` completo
        (que recarrega tudo do Jira), pra não pesar a rede num clique."""
        if ticket.chave in self._janelas_destacadas:
            painel = self._janelas_destacadas[ticket.chave]
            painel.atualizar_se_mostrando(ticket)
            painel.trazer_para_frente_com_atencao()
            self._fechar_anexado_se_visivel()
            return

        if self._painel_anexado.ticket_atual_chave() == ticket.chave:
            self._fechar_anexado_se_visivel()
            return

        self._painel_anexado.close()
        self._painel_anexado.deleteLater()
        self._painel_anexado = self._criar_painel_detalhes()
        self._painel_anexado.preparar_conteudo(ticket)

        largura = LARGURA_PAINEL_DETALHES
        x, lado, area = self._calcular_lado_e_x(largura)
        altura = min(self._painel_anexado.sizeHint().height(), area.height() - MARGEM_VERTICAL_TELA_PAINEL_DETALHES)
        y = self._calcular_y_clampado(area, altura)
        self._painel_anexado.mostrar(x, y, largura, int(altura), lado)

        if ticket.novo:
            self._provider.marcar_visto(ticket.chave)
            ticket.novo = False
            self._reconstruir_barra()

        self._atualizar_painel_se_aberto()

    def _fechar_anexado_se_visivel(self):
        """Fecha e descarta o painel anexado atual, se estiver visível
        mostrando ALGUM ticket - usado ao trazer uma janela DESTACADA pra
        frente (ver `_ticket_clicado`) pra nunca deixar dois tickets
        "selecionados" ao mesmo tempo (um destacado em foco + outro ainda
        aberto no slot anexado)."""
        if not self._painel_anexado.isVisible():
            return
        self._painel_anexado.close()
        self._painel_anexado.deleteLater()
        self._painel_anexado = self._criar_painel_detalhes()
        self._atualizar_painel_se_aberto()

    def _calcular_lado_e_x(self, largura):
        """Decide o lado (direita/esquerda) considerando o monitor ATUAL do
        Argus (2026-08-15, ver argus_painel_detalhes_ticket.md, "Múltiplos
        monitores") - prefere a direita; só vai pra esquerda se não couber na
        área útil do monitor (resolução/escala/barra de tarefas)."""
        tela = self.screen() or QGuiApplication.primaryScreen()
        area = tela.availableGeometry()
        x_direita = self.x() + self.width() + ESPACAMENTO_PAINEL_DETALHES
        if x_direita + largura <= area.right():
            return x_direita, "direita", area
        x_esquerda = max(area.left(), self.x() - ESPACAMENTO_PAINEL_DETALHES - largura)
        return x_esquerda, "esquerda", area

    def _calcular_y_clampado(self, area, altura):
        return max(area.top(), min(self.y(), area.bottom() - altura))

    def _alternar_destaque(self, painel):
        if painel.destacado:
            self._reanexar(painel)
        else:
            self._destacar(painel)

    def _destacar(self, painel):
        if len(self._janelas_destacadas) >= self._limite_janelas_destacadas:
            _DialogoAvisoLimite(self._limite_janelas_destacadas, self).exec()
            return
        ticket = painel._ticket
        x, y, largura, altura = self._geometria_para_destacar(painel)
        painel.tornar_destacado(x, y, largura, altura)
        self._janelas_destacadas[ticket.chave] = painel
        self._painel_anexado = self._criar_painel_detalhes()
        self._atualizar_painel_se_aberto()

    def _reanexar(self, painel):
        ticket = painel._ticket
        self._janelas_destacadas.pop(ticket.chave, None)
        painel.fechar_definitivo()
        self._ticket_clicado(ticket)

    def _geometria_para_destacar(self, painel):
        """Sem memória persistida entre sessões (2026-08-16, pedido do
        usuário: "se o problema é ficar salvando na memória posição de
        tickets, pode desconsiderar essa ideia") - parte sempre da posição
        atual do painel anexado, com uma cascata (`PASSO_CASCATA_JANELAS_DESTACADAS`
        × quantas já estão destacadas) só pra não nascerem exatamente
        empilhadas quando o usuário destaca vários seguidos."""
        largura, altura = painel.width(), max(painel.height(), 320)
        x, y = painel.x() + 24, painel.y() + 24
        deslocamento = len(self._janelas_destacadas) * PASSO_CASCATA_JANELAS_DESTACADAS
        x += deslocamento
        y += deslocamento
        tela = self.screen() or QGuiApplication.primaryScreen()
        area = tela.availableGeometry()
        largura = min(largura, area.width())
        altura = min(altura, area.height())
        x = max(area.left(), min(x, area.right() - largura))
        y = max(area.top(), min(y, area.bottom() - altura))
        return x, y, largura, altura

    def _fechar_painel_detalhes(self, painel):
        if painel.destacado:
            chave = painel.ticket_atual_chave()
            self._janelas_destacadas.pop(chave, None)
            painel.fechar_definitivo()
        else:
            # 🔥 Fecha e joga fora de vez (2026-08-16) - mesmo princípio da
            # simplificação de `_ticket_clicado`: sempre um slot anexado
            # NOVO/vazio depois de fechar, nunca uma instância "escondida"
            # reaproveitada por engano depois.
            painel.close()
            painel.deleteLater()
            self._painel_anexado = self._criar_painel_detalhes()
        self._atualizar_painel_se_aberto()

    def _abrir_ticket(self, ticket):
        webbrowser.open(ticket.url)
        self._provider.marcar_visto(ticket.chave)
        self.atualizar()

    # --- janela (pintura/máscara/posição) -------------------------------------

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        _pintar_fundo_janela(self, pintor, self._estado_janela)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if not self._estado_janela["cantos_ok"]:
            _aplicar_mascara_arredondada(self)

    def moveEvent(self, evento):
        """Recalcula a posição (e o lado) do painel anexado quando a janela
        principal se move - inclusive entre monitores (2026-08-15, ver
        argus_painel_detalhes_ticket.md, "Recalcular o lado de abertura
        quando o Argus mudar de monitor"). Janelas destacadas não seguem -
        elas são independentes por definição."""
        super().moveEvent(evento)
        if self._painel_anexado.isVisible() and not self._painel_anexado.destacado:
            largura = self._painel_anexado.width()
            altura = self._painel_anexado.height()
            x, lado, area = self._calcular_lado_e_x(largura)
            y = self._calcular_y_clampado(area, altura)
            self._painel_anexado.reposicionar(x, y, lado)

    def _persistir_posicao(self):
        self._persistencia.salvar_posicao_janela(self.x(), self.y())

    def closeEvent(self, evento):
        """Fechar a janela principal fecha o painel ANEXADO junto - janelas
        DESTACADAS permanecem abertas (2026-08-15, ver
        argus_painel_detalhes_ticket.md, "Fechamento")."""
        self._persistir_posicao()
        self._painel_anexado.esconder()
        super().closeEvent(evento)
