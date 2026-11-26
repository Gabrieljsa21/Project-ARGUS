"""Entrypoint standalone - `python -m argus.app`. Sobe a PRÓPRIA QApplication;
rodando dentro da GAIA, ela instancia `ArgusWidget` na QApplication que já
existe (ver ui/qt_painel.py) em vez de chamar isto.

🔥 Ícone na bandeja do sistema (2026-08-14) - a janela do widget é SEM BORDA de
propósito (ver core/widget.py), então não existe nenhum "X" pra fechar. Sem
isso, a única forma de encerrar seria o Gerenciador de Tarefas - mesmo padrão
que a GAIA já usa (ícone na bandeja controla o processo em segundo plano).

🔥 Erros de abertura visíveis (2026-11-12) - sem `.env` o Argus morria com
`KeyError` sem mostrar janela nenhuma; agora abre uma mensagem.

🔥 Log no padrão do ecossistema (2026-11-26) - `registro.configurar("ARGUS")`
grava em `%LOCALAPPDATA%/Ecossistema/ARGUS/Logs/AAAA-MM-DD.log` (30 dias),
com `print`, stderr e exceções não tratadas indo junto (pythonw não tem
console). Só aqui, no ponto de entrada: dentro da GAIA, os módulos do Argus
usam `logging.getLogger(__name__)` e caem no log da própria GAIA."""

import logging
import os
import sys

import requests
from dotenv import load_dotenv
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMenu

from . import registro
from .core.tema import aplicar_estilo_global
from .core.widget import ArgusWidget, mensagem_falha_jira
from .persistencia import PersistenciaArquivo
from .providers.jira_provider import JiraProvider

CAMINHO_ICONE = os.path.join(os.path.dirname(__file__), "assets", "icone_argus.ico")
# Log da 0.10.0 (antes do padrão do ecossistema); migrado na primeira abertura.
CAMINHOS_LOG_ANTIGO = [os.path.join(os.path.expanduser("~"), ".argus", nome) for nome in ("argus.log", "argus.log.1")]
VARIAVEIS_OBRIGATORIAS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
PASTA_LOGS = registro.pasta_logs("ARGUS")

log = logging.getLogger(__name__)


def migrar_log_antigo(pasta_logs, caminhos_antigos=CAMINHOS_LOG_ANTIGO) -> list:
    """Move o log da 0.10.0 (`~/.argus/argus.log` e `.log.1`) para a pasta
    nova, como `antigo-argus.log`/`antigo-argus.log.1`. A pasta `~/.argus`
    fica: ela guarda o `config.json` (estado e configurações). Devolve o que
    foi movido."""
    movidos = []
    for caminho in caminhos_antigos:
        if not os.path.exists(caminho):
            continue
        destino = os.path.join(pasta_logs, "antigo-" + os.path.basename(caminho))
        try:
            os.replace(caminho, destino)
            movidos.append(destino)
        except OSError as e:
            log.warning("Não consegui mover o log antigo %s: %s", caminho, e)
    return movidos


def _icone_bandeja() -> QIcon:
    """Ícone oficial do Argus (pavão de cristal, ver argus/assets/)."""
    return QIcon(CAMINHO_ICONE)


def _erro_de_abertura(texto: str) -> None:
    log.error("Não foi possível abrir: %s", texto)
    QMessageBox.critical(None, "Argus", f"{texto}\n\nLog em {PASTA_LOGS}")
    sys.exit(1)


def main():
    pasta_logs = registro.configurar("ARGUS")
    for destino in migrar_log_antigo(str(pasta_logs)):
        log.info("Log antigo movido para %s", destino)
    log.info("Argus aberto")
    load_dotenv()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(_icone_bandeja())
    aplicar_estilo_global(app)

    faltando = [nome for nome in VARIAVEIS_OBRIGATORIAS if not os.environ.get(nome)]
    if faltando:
        _erro_de_abertura(
            f"Faltam no .env: {', '.join(faltando)}.\n"
            "Copie o .env.example para .env e preencha (ver README)."
        )

    intervalo_segundos = int(os.environ.get("ARGUS_INTERVALO_POLLING_SEGUNDOS", "120"))
    limite_janelas_destacadas = int(os.environ.get("ARGUS_LIMITE_JANELAS_DESTACADAS", "5"))

    persistencia = PersistenciaArquivo()
    try:
        provider = JiraProvider(
            os.environ["JIRA_BASE_URL"], os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"], persistencia,
        )
    except requests.RequestException as e:
        _erro_de_abertura(mensagem_falha_jira(str(e)))

    widget = ArgusWidget(provider, persistencia, limite_janelas_destacadas=limite_janelas_destacadas)
    widget.show()

    timer = QTimer()
    timer.timeout.connect(widget.atualizar)
    timer.start(intervalo_segundos * 1000)

    menu_bandeja = QMenu()
    menu_bandeja.addAction("Atualizar agora", widget.atualizar)
    menu_bandeja.addAction("Configurações...", widget.abrir_configuracoes)
    menu_bandeja.addAction("Abrir logs", lambda: os.startfile(PASTA_LOGS))
    menu_bandeja.addSeparator()
    menu_bandeja.addAction("Fechar Argus", app.quit)

    bandeja = QSystemTrayIcon(_icone_bandeja())
    bandeja.setToolTip("Argus")
    bandeja.setContextMenu(menu_bandeja)
    bandeja.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
