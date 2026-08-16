"""Paleta visual do Argus - MESMOS valores hex do Painel da GAIA
(assistant/ui/qt_widgets.py), copiados aqui (não importados - o Argus não
depende de código da GAIA, só do visual dela) pra não parecer um programa
diferente quando os dois rodam lado a lado no mesmo desktop (2026-08-14,
pedido do usuário: "quero q mantenha o padrão da paleta da gaia, proximo ao
menu radial")."""

BG_COLOR = "#0d0d0f"
SURFACE_COLOR = "#1a1a1d"
HIGHLIGHT_COLOR = "#28282c"
BORDA_SUTIL = "#2f2f34"
GAIA_GOLD = "#d4af6a"
GAIA_GOLD_HOVER = "#e3c284"
GAIA_SILVER = "#d9d9dc"
TEXT_COLOR = "#f1efe9"
TEXT_DIM = "#8f8d8a"
FONTE_BASE = "Segoe UI"


def aplicar_estilo_global(app):
    """Chamado 1x na criação da QApplication (ver app.py) - MESMO tratamento
    que `ui/qt_widgets.py::aplicar_estilo_global` já faz no Painel da GAIA,
    copiado aqui (2026-08-14, pedido do usuário: "as barras de rolagem,
    dropdowns e tudo tem que seguir o padrão GAIA"). Força o estilo "Fusion"
    (sem isso o Windows usa o tema nativo pra scrollbar/dropdown, que ignora
    boa parte do QSS de cor) e troca a barra de rolagem cinza nativa por uma
    versão fina dourada, sem botão de seta em cada ponta."""
    app.setStyle("Fusion")
    app.setStyleSheet(f"""
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {GAIA_GOLD};
            border-radius: 5px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {GAIA_GOLD_HOVER};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
            background: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {GAIA_GOLD};
            border-radius: 5px;
            min-width: 24px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {GAIA_GOLD_HOVER};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            border: none;
            background: none;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}
    """)
