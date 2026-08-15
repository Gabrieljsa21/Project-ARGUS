"""Entrypoint standalone - `python -m argus.app`. Sobe a PRÓPRIA QApplication;
rodando dentro da GAIA, ela instancia `ArgusWidget` na QApplication que já
existe (ver ui/qt_painel.py) em vez de chamar isto."""

import os
import sys

from dotenv import load_dotenv
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .core.widget import ArgusWidget
from .persistencia import PersistenciaArquivo
from .providers.jira_provider import JiraProvider


def main():
    load_dotenv()
    base_url = os.environ["JIRA_BASE_URL"]
    email = os.environ["JIRA_EMAIL"]
    token = os.environ["JIRA_API_TOKEN"]
    intervalo_segundos = int(os.environ.get("ARGUS_INTERVALO_POLLING_SEGUNDOS", "120"))

    persistencia = PersistenciaArquivo()
    provider = JiraProvider(base_url, email, token, persistencia)

    app = QApplication(sys.argv)
    widget = ArgusWidget(provider, persistencia)
    widget.show()

    timer = QTimer()
    timer.timeout.connect(widget.atualizar)
    timer.start(intervalo_segundos * 1000)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
