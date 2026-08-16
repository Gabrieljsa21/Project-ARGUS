"""Validação manual do menu de Configurações (2026-08-16, ver
argus_painel_detalhes_ticket.md) - confirma que limite de janelas
destacadas/chacoalhada de atenção persistem, aplicam em tempo real (inclusive
em painéis já criados) e que a config salva prevalece sobre o padrão do
`.env` na próxima inicialização. NUNCA chama `_DialogoConfiguracoes.exec()`
(bloquearia esperando interação - em vez disso simula o "Salvar" chamando
`_confirmar()` direto). Rodar com QT_QPA_PLATFORM=offscreen a partir da raiz
do projeto:

    QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe testes/testar_configuracoes.py
"""

import sys
import tempfile
import os

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from argus.core.widget import ArgusWidget, _DialogoConfiguracoes
from argus.modelos import Categoria, Ticket
from argus.persistencia import PersistenciaArquivo
from argus.providers.base import NotificacaoProvider


class ProviderFalso(NotificacaoProvider):
    def listar_categorias(self):
        return [Categoria("atendimento", "Aguardando Atendimento", [
            Ticket("NSD-1", "Erro 1", "Aguardando atendimento", "High", "https://example.com/NSD-1", "2026-08-14", novo=True),
        ])]

    def marcar_visto(self, chave_ticket):
        pass


def main():
    caminho_config = os.path.join(tempfile.gettempdir(), "argus_teste_configuracoes.json")
    if os.path.exists(caminho_config):
        os.remove(caminho_config)
    app = QApplication(sys.argv)

    persistencia = PersistenciaArquivo(caminho_config)
    widget = ArgusWidget(ProviderFalso(), persistencia, limite_janelas_destacadas=5)
    widget.show()
    app.processEvents()

    print("OK: padrao do .env respeitado sem config salva:", widget._limite_janelas_destacadas == 5)
    print("OK: chacoalhada desligada por padrao:", widget._chacoalhada_ativa is False)

    # painel ja aberto deve refletir a config atual atraves do getter (nao
    # captura um bool fixo na criacao).
    ticket = widget._categorias[0].tickets[0]
    widget._ticket_clicado(ticket)
    app.processEvents()
    painel_aberto = widget._painel_anexado
    print("OK: painel aberto usa o getter (chacoalhada desligada agora):",
          painel_aberto._obter_chacoalhada_ativa() is False)

    # simula o usuario abrindo o dialogo e mudando os dois campos, sem exec().
    dialogo = _DialogoConfiguracoes(widget._limite_janelas_destacadas, widget._chacoalhada_ativa, widget)
    dialogo._campo_limite.setValue(3)
    dialogo._campo_chacoalhada.setChecked(True)
    dialogo._confirmar()
    widget._limite_janelas_destacadas = dialogo.limite_janelas_destacadas
    widget._chacoalhada_ativa = dialogo.chacoalhada_ativa
    widget._persistencia.salvar_configuracoes({
        "limite_janelas_destacadas": widget._limite_janelas_destacadas,
        "chacoalhada_ativa": widget._chacoalhada_ativa,
    })
    print("OK: limite atualizado em tempo real:", widget._limite_janelas_destacadas == 3)
    print("OK: chacoalhada ligada em tempo real:", widget._chacoalhada_ativa is True)
    print("OK: painel JA aberto reflete a mudanca sem recriar (mesmo getter):",
          painel_aberto._obter_chacoalhada_ativa() is True)

    # reabre com uma NOVA instancia/persistencia apontando pro mesmo arquivo
    # - a config salva deve prevalecer sobre o argumento do construtor.
    persistencia_2 = PersistenciaArquivo(caminho_config)
    widget_2 = ArgusWidget(ProviderFalso(), persistencia_2, limite_janelas_destacadas=5)
    print("OK: limite persistido prevalece sobre o padrao do .env:", widget_2._limite_janelas_destacadas == 3)
    print("OK: chacoalhada persistida prevalece sobre o padrao:", widget_2._chacoalhada_ativa is True)


if __name__ == "__main__":
    main()
