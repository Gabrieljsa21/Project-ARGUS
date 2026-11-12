"""Diálogos do Argus (comentário, rascunho de análise, log de mudanças,
aviso de limite e Configurações). Saíram de `widget.py` (2026-11-12)."""

from datetime import datetime

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QApplication,
    QDialog, QTextEdit, QPlainTextEdit, QFrame,
)

from .tema import (
    BG_COLOR, SURFACE_COLOR, BORDA_SUTIL,
    TEXT_COLOR, TEXT_DIM,
)
from ..modelos import PERFIL_N1, PERFIL_N2, perfil_configurado
from .componentes import (
    LIMITE_JANELAS_DESTACADAS_PADRAO, ATIVAR_CHACOALHADA_ATENCAO,
    _botao_estilizado, _titulo_secao, _descricao, SpinboxCapsula, Switch,
)


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


class _DialogoLogMudancas(QDialog):
    """O que gerou o aviso do ticket (2026-10-08, ver `Ticket.mudancas`) -
    uma linha por mudança desde o último visto, só leitura."""

    def __init__(self, ticket, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Log - {ticket.chave}")
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self.resize(420, 240)

        lay = QVBoxLayout(self)
        if ticket.mudancas_vistas_em:
            try:
                quando = datetime.fromisoformat(ticket.mudancas_vistas_em).strftime("%d/%m %H:%M")
            except ValueError:
                quando = ticket.mudancas_vistas_em
            cabecalho = f"Último aviso, visto em {quando}:"
        else:
            cabecalho = "Mudanças desde a última vez que você abriu:"
        lay.addWidget(_descricao(cabecalho))

        self._texto = QTextEdit()
        self._texto.setReadOnly(True)
        self._texto.setPlainText("\n".join(f"• {item}" for item in ticket.mudancas))
        self._texto.setStyleSheet(
            f"background-color: {SURFACE_COLOR}; color: {TEXT_COLOR}; border: 1px solid {BORDA_SUTIL}; border-radius: 6px;"
        )
        lay.addWidget(self._texto, 1)

        linha_botoes = QHBoxLayout()
        linha_botoes.addStretch(1)
        botao_fechar = _botao_estilizado("Fechar", preenchido=True)
        botao_fechar.clicked.connect(self.accept)
        linha_botoes.addWidget(botao_fechar)
        lay.addLayout(linha_botoes)


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

    def __init__(self, limite_atual, chacoalhada_ativa, parent=None, perfil_n2=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações do Argus")
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self.resize(380, 360)
        self.limite_janelas_destacadas = limite_atual
        self.chacoalhada_ativa = chacoalhada_ativa
        self.perfil_n2 = perfil_n2

        lay = QVBoxLayout(self)
        if perfil_n2 is not None:
            lay.addWidget(self._card_perfil(perfil_n2))
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

    def _card_perfil(self, perfil_n2) -> QFrame:
        """Perfil N1/N2 (2026-10-01, ver docs/ARQUITETURA.md "Perfil N1/N2") -
        o Argus não sabe o que é Jira; só grava a escolha, quem interpreta é
        o provider (`JiraProvider.perfil`)."""
        frame, lay_frame = self._card()
        lay_frame.addWidget(_titulo_secao("Perfil de atendimento"))
        lay_frame.addWidget(_descricao(
            "N1 acompanha os chamados do Service Desk atribuídos a você, por "
            "status. N2 acompanha os tickets de desenvolvimento (Platz, "
            "Bahn e SDP) atribuídos a você, com o SLA do chamado de origem."
        ))
        self._campo_perfil = Switch("N2 - Platz e Bahn", "N1 - Service Desk", marcado=perfil_n2)
        lay_frame.addWidget(self._campo_perfil)
        return frame

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
        if self.perfil_n2 is not None:
            self.perfil_n2 = self._campo_perfil.isChecked()
        self.accept()


def salvar_configuracoes_do_dialogo(persistencia, dialogo) -> dict:
    """Grava o que o usuário escolheu MESCLANDO com o que já estava salvo
    (opção que o dialog não conhece nunca é apagada). Devolve o dict salvo."""
    configuracoes = persistencia.obter_configuracoes()
    configuracoes.update({
        "limite_janelas_destacadas": dialogo.limite_janelas_destacadas,
        "chacoalhada_ativa": dialogo.chacoalhada_ativa,
    })
    if dialogo.perfil_n2 is not None:
        configuracoes["perfil"] = PERFIL_N2 if dialogo.perfil_n2 else PERFIL_N1
    persistencia.salvar_configuracoes(configuracoes)
    return configuracoes


def abrir_configuracoes_argus(
    persistencia, parent=None, com_perfil=True, limite_atual=None, chacoalhada_atual=None,
) -> dict | None:
    """Tela de Configurações NATIVA do Argus (2026-10-01, pedido do usuário:
    "assim como o loki, o argus deveria ter sua propria tela de config. E a
    gaia pega dele") - fonte única das opções do Argus, aberta pela bandeja
    no uso standalone (via `ArgusWidget.abrir_configuracoes`) e pela GAIA
    mesmo sem o widget aberto. Quem embute o Argus nunca duplica estes
    campos; só acrescenta na própria UI o que é dele (ex.: voz na GAIA).

    Devolve o dict salvo, ou None se o usuário cancelou."""
    config = persistencia.obter_configuracoes()
    dialogo = _DialogoConfiguracoes(
        limite_atual if limite_atual is not None else config.get("limite_janelas_destacadas", LIMITE_JANELAS_DESTACADAS_PADRAO),
        chacoalhada_atual if chacoalhada_atual is not None else config.get("chacoalhada_ativa", ATIVAR_CHACOALHADA_ATENCAO),
        parent,
        perfil_n2=(perfil_configurado(config) == PERFIL_N2) if com_perfil else None,
    )
    if dialogo.exec() != QDialog.Accepted:
        return None
    return salvar_configuracoes_do_dialogo(persistencia, dialogo)


