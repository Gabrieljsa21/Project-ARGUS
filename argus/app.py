"""Entrypoint standalone - `python -m argus.app`. Sobe a PRÓPRIA QApplication;
rodando dentro da GAIA, ela instancia `ArgusWidget` na QApplication que já
existe (ver ui/qt_painel.py) em vez de chamar isto.

🔥 Ícone na bandeja do sistema (2026-08-14) - a janela do widget é SEM BORDA de
propósito (ver core/widget.py), então não existe nenhum "X" pra fechar. Sem
isso, a única forma de encerrar seria o Gerenciador de Tarefas - mesmo padrão
que a GAIA já usa (ícone na bandeja controla o processo em segundo plano)."""

import os
import sys

from dotenv import load_dotenv
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from .core.tema import aplicar_estilo_global
from .core.widget import ArgusWidget
from .persistencia import PersistenciaArquivo
from .providers.jira_provider import JiraProvider

CAMINHO_ICONE = os.path.join(os.path.dirname(__file__), "assets", "icone_argus.ico")


def _icone_bandeja() -> QIcon:
    """Ícone oficial do Argus (pavão de cristal, ver argus/assets/)."""
    return QIcon(CAMINHO_ICONE)


def main():
    load_dotenv()
    base_url = os.environ["JIRA_BASE_URL"]
    email = os.environ["JIRA_EMAIL"]
    token = os.environ["JIRA_API_TOKEN"]
    intervalo_segundos = int(os.environ.get("ARGUS_INTERVALO_POLLING_SEGUNDOS", "120"))
    limite_janelas_destacadas = int(os.environ.get("ARGUS_LIMITE_JANELAS_DESTACADAS", "5"))

    persistencia = PersistenciaArquivo()
    provider = JiraProvider(base_url, email, token, persistencia)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(_icone_bandeja())
    aplicar_estilo_global(app)

    widget = ArgusWidget(provider, persistencia, limite_janelas_destacadas=limite_janelas_destacadas)
    widget.show()

    timer = QTimer()
    timer.timeout.connect(widget.atualizar)
    timer.start(intervalo_segundos * 1000)

    menu_bandeja = QMenu()
    menu_bandeja.addAction("Atualizar agora", widget.atualizar)
    menu_bandeja.addAction("Configurações...", widget.abrir_configuracoes)
    menu_bandeja.addSeparator()
    menu_bandeja.addAction("Fechar Argus", app.quit)

    bandeja = QSystemTrayIcon(_icone_bandeja())
    bandeja.setToolTip("Argus")
    bandeja.setContextMenu(menu_bandeja)
    bandeja.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
