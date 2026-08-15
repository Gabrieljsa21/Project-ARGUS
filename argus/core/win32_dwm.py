"""Cantos arredondados de verdade via DWM nativo do Windows 11, em vez de
pintar/mascarar manualmente (`QPainterPath` + `setMask`) - achado pesquisando
`amnweb/yasb` (`Pesquisas de Repositorios/pesquisa-yasb.md`, 2026-08-15): o
mascaramento manual foi a causa raiz do bug de encolhimento que o Argus teve
(a máscara precisava ser recalculada a cada resize, e ficava dessincronizada
por 1 volta do event loop até o `QTimer.singleShot` corrigir). O Windows já
faz isso de graça pra qualquer janela sem borda - só precisa pedir via
`DwmSetWindowAttribute`. Mesma chamada usada pelo `amnweb/yasb`
(`core/utils/win32/backdrop.py`), sem nenhuma dependência do PyQt6 deles -
é ctypes puro, funciona igual em cima do PySide6."""

import ctypes
import sys

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWA_COLOR_NONE = 0xFFFFFFFE
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_MICA_EFFECT = 1029  # atributo não documentado, só builds 22000-22620 (ver aplicar_mica)
DWMWCP_ROUND = 2
DWMSBT_MAINWINDOW = 2  # "Mica" de verdade (build 22621+)


class _MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


def aplicar_cantos_redondos(widget) -> bool:
    """Pede ao Windows pra arredondar os cantos da janela nativamente - só
    funciona no Windows 11 (build 22000+). Devolve True se aplicou, False se
    não deu (Windows mais antigo, não-Windows, ou qualquer erro) - quem chama
    decide se cai pro mascaramento manual como alternativa nesse caso."""
    if sys.platform != "win32":
        return False
    try:
        if sys.getwindowsversion().build < 22000:
            return False
        hwnd = int(widget.winId())
        preferencia = ctypes.c_int(DWMWCP_ROUND)
        resultado = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(preferencia), ctypes.sizeof(preferencia)
        )
        return resultado == 0
    except Exception:
        return False


def remover_cor_borda(widget) -> bool:
    """Pede ao Windows pra NÃO desenhar a cor de accent do sistema ao redor
    da janela - o Argus já pinta a própria borda sutil (`BORDA_SUTIL`, ver
    `widget.py`), a borda nativa por cima ficaria redundante/destoante."""
    if sys.platform != "win32":
        return False
    try:
        hwnd = int(widget.winId())
        cor = ctypes.c_int(DWMWA_COLOR_NONE)
        resultado = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_BORDER_COLOR, ctypes.byref(cor), ctypes.sizeof(cor)
        )
        return resultado == 0
    except Exception:
        return False


def aplicar_mica(widget) -> bool:
    """Fundo "Mica" nativo do Windows 11 - amostra o papel de parede/cor do
    desktop por trás da janela, em vez do preenchimento sólido pintado à mão.
    Precisa estender o "frame" pra dentro da área do cliente inteira primeiro
    (`DwmExtendFrameIntoClientArea` com margem -1 em todos os lados - "cobre
    tudo") pro Mica renderizar atrás do conteúdo todo, não só de uma borda.

    🔥 Atenção de quem for ATIVAR isso (não é automático) - Mica só aparece de
    verdade se o preenchimento próprio (`ArgusWidget.paintEvent`) usar um
    alpha BEM mais baixo que os 235/255 atuais - do jeito que está hoje, o
    preenchimento quase opaco esconde o material por trás. Ativar isso é uma
    mudança de identidade visual (de "card sólido" pra "vidro fosco"), não só
    uma chamada técnica - testar visualmente antes de decidir manter."""
    if sys.platform != "win32":
        return False
    try:
        build = sys.getwindowsversion().build
        if build < 22000:
            return False
        hwnd = int(widget.winId())
        margens = _MARGINS(-1, -1, -1, -1)
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margens))
        if build >= 22621:
            valor = ctypes.c_int(DWMSBT_MAINWINDOW)
            resultado = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(valor), ctypes.sizeof(valor)
            )
        else:
            valor = ctypes.c_int(1)
            resultado = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_MICA_EFFECT, ctypes.byref(valor), ctypes.sizeof(valor)
            )
        return resultado == 0
    except Exception:
        return False
