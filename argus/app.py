"""Entrypoint standalone - `python -m argus.app`. Sobe a PRÓPRIA QApplication;
rodando dentro da GAIA, ela instancia `ArgusWidget` na QApplication que já
existe (ver ui/qt_painel.py) em vez de chamar isto.

🔥 Ícone na bandeja do sistema (2026-08-14) - a janela do widget é SEM BORDA de
propósito (ver core/widget.py), então não existe nenhum "X" pra fechar. Sem
isso, a única forma de encerrar seria o Gerenciador de Tarefas - mesmo padrão
que a GAIA já usa (ícone na bandeja controla o processo em segundo plano).

🔥 Log em arquivo e erros de abertura visíveis (2026-11-12) - iniciado pelo
`.vbs` oculto (pythonw), todo `print` se perdia; e sem `.env` o Argus morria
com `KeyError` sem mostrar janela nenhuma. Agora a saída vai também para
`~/.argus/argus.log` e os problemas de configuração abrem uma mensagem."""

import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMenu

from .core.tema import aplicar_estilo_global
from .core.widget import ArgusWidget, mensagem_falha_jira
from .persistencia import PersistenciaArquivo
from .providers.jira_provider import JiraProvider

CAMINHO_ICONE = os.path.join(os.path.dirname(__file__), "assets", "icone_argus.ico")
CAMINHO_LOG = os.path.join(os.path.expanduser("~"), ".argus", "argus.log")
# Ao abrir, um log maior que isso vira `argus.log.1` (só um arquivo antigo).
TAMANHO_MAXIMO_LOG_BYTES = 1_000_000
VARIAVEIS_OBRIGATORIAS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")


class _SaidaComLog:
    """Repete cada linha escrita no console (se houver um) no arquivo de log,
    com data e hora no começo de cada linha."""

    def __init__(self, original, arquivo):
        self._original = original
        self._arquivo = arquivo
        self._inicio_de_linha = True

    def write(self, texto):
        if self._original is not None:
            try:
                self._original.write(texto)
            except Exception:
                pass
        for pedaco in texto.splitlines(keepends=True):
            if self._inicio_de_linha:
                self._arquivo.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S "))
            self._arquivo.write(pedaco)
            self._inicio_de_linha = pedaco.endswith("\n")
        self._arquivo.flush()
        return len(texto)

    def flush(self):
        if self._original is not None:
            try:
                self._original.flush()
            except Exception:
                pass
        self._arquivo.flush()


def _configurar_log() -> None:
    os.makedirs(os.path.dirname(CAMINHO_LOG), exist_ok=True)
    if os.path.exists(CAMINHO_LOG) and os.path.getsize(CAMINHO_LOG) > TAMANHO_MAXIMO_LOG_BYTES:
        os.replace(CAMINHO_LOG, CAMINHO_LOG + ".1")
    arquivo = open(CAMINHO_LOG, "a", encoding="utf-8")
    sys.stdout = _SaidaComLog(sys.stdout, arquivo)
    sys.stderr = _SaidaComLog(sys.stderr, arquivo)


def _icone_bandeja() -> QIcon:
    """Ícone oficial do Argus (pavão de cristal, ver argus/assets/)."""
    return QIcon(CAMINHO_ICONE)


def _erro_de_abertura(texto: str) -> None:
    print(f"[Argus] Não foi possível abrir: {texto}")
    QMessageBox.critical(None, "Argus", f"{texto}\n\nDetalhes em {CAMINHO_LOG}")
    sys.exit(1)


def main():
    _configurar_log()
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
    menu_bandeja.addAction("Abrir log", lambda: os.startfile(CAMINHO_LOG))
    menu_bandeja.addSeparator()
    menu_bandeja.addAction("Fechar Argus", app.quit)

    bandeja = QSystemTrayIcon(_icone_bandeja())
    bandeja.setToolTip("Argus")
    bandeja.setContextMenu(menu_bandeja)
    bandeja.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
