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


WCA_ACCENT_POLICY = 19
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4


class _MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


class _ACCENTPOLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_uint),
        ("AccentFlags", ctypes.c_uint),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_uint),
    ]


class _WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.POINTER(ctypes.c_int)),
        ("SizeOfData", ctypes.c_size_t),
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


def _cor_para_gradiente(cor_hex: str, alpha: int) -> int:
    """"#RRGGBB" + alpha (0-255) -> inteiro AABBGGRR que a struct ACCENTPOLICY
    espera - a mesma conversão que o amnweb/yasb faz em `HEXtoRGBAint`."""
    cor_hex = cor_hex.lstrip("#")
    r = int(cor_hex[0:2], 16)
    g = int(cor_hex[2:4], 16)
    b = int(cor_hex[4:6], 16)
    return (alpha << 24) | (b << 16) | (g << 8) | r


def aplicar_acrylic(widget, cor_hex: str = "#1a1a1d", alpha: int = 200) -> bool:
    """Acrylic (API não documentada `SetWindowCompositionAttribute`, Win10+) -
    diferente do Mica, aceita uma cor de "tingimento" própria (`GradientColor`)
    em vez de só amostrar o desktop cru - dá pra manter escuro/dourado da
    GAIA em vez do material claro que o Mica mostrou. `alpha` controla o
    quanto o tingimento domina sobre o blur (mais alto = mais sólido/escuro,
    mais baixo = mais transparente/blur aparece mais)."""
    if sys.platform != "win32":
        return False
    try:
        hwnd = int(widget.winId())
        accent = _ACCENTPOLICY()
        accent.AccentState = ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 0
        accent.GradientColor = _cor_para_gradiente(cor_hex, alpha)
        accent.AnimationId = 0

        data = _WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = WCA_ACCENT_POLICY
        data.SizeOfData = ctypes.sizeof(accent)
        data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.POINTER(ctypes.c_int))

        resultado = ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        return resultado != 0  # 🔥 API de user32/BOOL - 0 é FALHA aqui, oposto do HRESULT do dwmapi acima
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
