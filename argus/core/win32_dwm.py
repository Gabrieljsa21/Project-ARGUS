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
DWMWCP_ROUND = 2


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
