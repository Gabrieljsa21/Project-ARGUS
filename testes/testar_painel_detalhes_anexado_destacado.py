"""Validação manual do painel de detalhes anexado/destacado (2026-08-15, ver
argus_painel_detalhes_ticket.md e ARQUITETURA.md) - sobe a janela com um
provider FALSO e exercita: abrir no anexado, trocar pra outro ticket (fecha
o painel anterior e abre um novo, sem crossfade - ver correção 2026-08-16 em
`_ticket_clicado`), nunca abrir 2 instâncias do mesmo ticket, destacar/
reanexar, fechar cada modo. Rodar com QT_QPA_PLATFORM=offscreen a partir da
raiz do projeto:

    QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe testes/testar_painel_detalhes_anexado_destacado.py
"""

import sys
import tempfile
import os

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from argus.core.widget import ArgusWidget, _LinhaTicket, _AlcaArraste, _RotuloClicavel
from argus.modelos import Categoria, Ticket
from argus.persistencia import PersistenciaArquivo
from argus.providers.base import NotificacaoProvider


class ProviderFalso(NotificacaoProvider):
    def listar_categorias(self):
        return [
            Categoria("atendimento", "Aguardando Atendimento", [
                Ticket("NSD-1", "Erro 1", "Aguardando atendimento", "High", "https://example.com/NSD-1", "2026-08-14", novo=True),
                Ticket("NSD-2", "Erro 2", "Aguardando atendimento", "Medium", "https://example.com/NSD-2", "2026-08-14", novo=True),
            ]),
        ]

    def marcar_visto(self, chave_ticket):
        pass


def main():
    caminho_config = os.path.join(tempfile.gettempdir(), "argus_teste_painel_config.json")
    if os.path.exists(caminho_config):
        os.remove(caminho_config)
    app = QApplication(sys.argv)
    widget = ArgusWidget(ProviderFalso(), PersistenciaArquivo(caminho_config), limite_janelas_destacadas=2)
    widget.show()
    app.processEvents()

    ticket_1 = widget._categorias[0].tickets[0]
    ticket_2 = widget._categorias[0].tickets[1]

    def _chaves_selecionadas():
        # so conta linhas VISIVEIS (2026-08-16) - `deleteLater()` demora ate a
        # proxima volta do loop de eventos pra destruir de verdade a linha
        # antiga; o que importa pro usuario e o que esta escondido na hora
        # (ver correcao de `_preencher_painel`/`hide()`), nao o que ainda
        # existe em memoria esperando ser coletado.
        linhas = widget._painel.findChildren(_LinhaTicket)
        return {l._ticket.chave for l in linhas if l._selecionado and l.isVisible()}

    # abre a lista da categoria (hover) pra acompanhar o destaque persistente
    # na lista enquanto seleciona tickets diferentes.
    widget._hover_entrou_categoria(widget._categorias[0])
    app.processEvents()

    widget._ticket_clicado(ticket_1)
    app.processEvents()
    print("OK: anexado mostra NSD-1:", widget._painel_anexado.ticket_atual_chave() == "NSD-1")
    print("OK: anexado visivel:", widget._painel_anexado.isVisible())
    print("OK: so NSD-1 destacado na lista:", _chaves_selecionadas() == {"NSD-1"})

    # 🔥 regressao (2026-08-16, pedido do usuario: "a barra de arraste, qnd
    # estiver vinculada a barra dos status, tem q mover TUDO, a barra dos
    # status tbm") - arrastar a barra do painel ANEXADO tem que mover a
    # janela PRINCIPAL (o painel ja segue ela sozinho via moveEvent), nao só
    # o painel isolado.
    class _EventoFalsoArraste:
        def __init__(self, ponto):
            self._ponto = ponto

        def globalPosition(self):
            return self

        def toPoint(self):
            return self._ponto

    from PySide6.QtCore import QPoint as _QPoint
    alca_anexada = widget._painel_anexado.findChildren(_AlcaArraste)[0]
    pos_principal_antes = widget.pos()
    pos_painel_antes = widget._painel_anexado.pos()
    alca_anexada.mousePressEvent(_EventoFalsoArraste(_QPoint(300, 300)))
    alca_anexada.mouseMoveEvent(_EventoFalsoArraste(_QPoint(350, 340)))
    alca_anexada.mouseReleaseEvent(_EventoFalsoArraste(_QPoint(350, 340)))
    app.processEvents()  # moveEvent do topo-nivel pode ser entregue so na volta ao loop de eventos
    deslocamento_principal = widget.pos() - pos_principal_antes
    print("OK: arrastar a barra anexada move a janela PRINCIPAL:", (deslocamento_principal.x(), deslocamento_principal.y()) == (50, 40))
    # confere que o painel segue a formula "ao lado da principal" pra
    # posicao ATUAL (nao um deslocamento fixo em pixels - a tela virtual
    # offscreen usada no teste e pequena, 800x800, entao o clamp de nao
    # sair da tela pode legitimamente prender o X sem branda relacao com o
    # simples delta do arraste; o que importa e a formula bater).
    x_esperado, lado_esperado, area_esperada = widget._calcular_lado_e_x(widget._painel_anexado.width())
    y_esperado = widget._calcular_y_clampado(area_esperada, widget._painel_anexado.height())
    print(
        "OK: o painel anexado segue a posicao recalculada da principal (moveEvent):",
        (widget._painel_anexado.x(), widget._painel_anexado.y()) == (x_esperado, y_esperado),
    )

    # clicar de novo no MESMO ticket - não deve fechar/recriar nada.
    painel_nsd1 = widget._painel_anexado
    widget._ticket_clicado(ticket_1)
    print("OK: mesma instancia ao clicar de novo no mesmo ticket:", widget._painel_anexado is painel_nsd1)

    # 🔥 troca SEM crossfade (2026-08-16, simplificação pedida pelo usuário
    # depois de bugs reais em uso: "clicou no ticket apareceu ele do lado,
    # clicou em outro ticket, some o anterior e abre o novo") - fecha o
    # painel de NSD-1 e abre uma instância NOVA pra NSD-2, na hora, sem
    # animação/estado intermediário esperando um timer.
    widget._ticket_clicado(ticket_2)
    print("OK: painel antigo (NSD-1) foi fechado:", not painel_nsd1.isVisible())
    print("OK: virou uma instancia NOVA pra NSD-2:", widget._painel_anexado is not painel_nsd1)
    print("OK: anexado mostra NSD-2 na hora, sem esperar animacao:", widget._painel_anexado.ticket_atual_chave() == "NSD-2")
    app.processEvents()  # deixa o deleteLater() do painel antigo rodar
    print("OK: NSD-1 desselecionado e so NSD-2 destacado na lista:", _chaves_selecionadas() == {"NSD-2"})

    # 🔥 regressao do bug "os tickets estao se sobrepondo ao selecionar
    # varios" - a causa raiz era `deleteLater()` sozinho ao reconstruir a
    # lista: o widget antigo continua VISIVEL (na posicao antiga, sobreposto
    # ao conteudo novo) ate uma volta futura do loop de eventos - `hide()`
    # tem que esconder na hora, SEM esperar nenhum `processEvents()`.
    linhas_antes = widget._painel.findChildren(_LinhaTicket)
    widget._preencher_painel(widget._categorias[0])  # reconstroi de novo, sem devolver ao loop de eventos
    todas_antigas_escondidas = all(not l.isVisible() for l in linhas_antes)
    print("OK: linhas antigas escondidas na hora (sem sobrepor), antes do deleteLater rodar:", todas_antigas_escondidas)

    # destacar o painel atual (NSD-2) - vira janela independente, anexado
    # ganha uma instância NOVA e vazia.
    painel_destacado = widget._painel_anexado
    widget._alternar_destaque(painel_destacado)
    print("OK: NSD-2 registrado como destacado:", "NSD-2" in widget._janelas_destacadas)
    print("OK: painel anexado agora e outra instancia (vazia):", widget._painel_anexado is not painel_destacado)
    print("OK: anexado novo esta sem ticket:", widget._painel_anexado.ticket_atual_chave() is None)
    print("OK: janela destacada continua com NSD-2:", painel_destacado.ticket_atual_chave() == "NSD-2")
    app.processEvents()
    # so conta as VISIVEIS (2026-08-16) - `preparar_conteudo` ja rodou mais
    # de uma vez nesta mesma instancia (uma vez ao abrir no anexado, outra
    # ao destacar), e a barra antiga so e destruida numa volta futura do
    # loop de eventos (deleteLater) - o que importa e quantas estao
    # VISIVEIS agora, nao quantas ainda existem em memoria esperando GC.
    alcas = [a for a in painel_destacado.findChildren(_AlcaArraste) if a.isVisible()]
    print("OK: destacado tem exatamente 1 barra de arraste visivel:", len(alcas) == 1)

    # 🔥 regressao do bug relatado com print de tela: "quando clico no
    # desfixar ele zoa os botoes, como acontecia com o redimensionar antes
    # de removermos" - causa raiz real (2026-08-16): `preparar_conteudo`
    # rodando mais de uma vez na MESMA instancia (aqui: uma vez ao abrir no
    # anexado, outra ao destacar) deixava titulo/botoes ANTIGOS orfaos e
    # visiveis (a limpeza do layout so alcancava o nivel 1, nunca entrava
    # nos sub-layouts linha_topo/linha_arraste/linha_botoes - ver
    # `_limpar_layout`). Chama `preparar_conteudo` de novo (3a vez nesta
    # mesma instancia) pra confirmar que nao duplica mais nada.
    painel_destacado.preparar_conteudo(painel_destacado._ticket)
    app.processEvents()
    titulos_visiveis = [t for t in painel_destacado.findChildren(_RotuloClicavel) if t.isVisible()]
    alcas_visiveis = [a for a in painel_destacado.findChildren(_AlcaArraste) if a.isVisible()]
    print("OK: sem duplicar titulo apos preparar_conteudo rodar de novo:", len(titulos_visiveis) == 1)
    print("OK: sem duplicar barra de arraste tambem:", len(alcas_visiveis) == 1)

    # 🔥 regressao: "eu so quero poder arrastar o ticket, o que atualmente
    # nao esta funcionando" (2026-08-16) - simula pressionar+mover+soltar na
    # barra de arraste e confere que a JANELA (nao so a barra) se moveu.
    class _EventoFalso:
        def __init__(self, ponto):
            self._ponto = ponto

        def globalPosition(self):
            return self

        def toPoint(self):
            return self._ponto

    from PySide6.QtCore import QPoint
    alca = alcas_visiveis[0]
    posicao_antes = painel_destacado.pos()
    alca.mousePressEvent(_EventoFalso(QPoint(500, 500)))
    alca.mouseMoveEvent(_EventoFalso(QPoint(560, 540)))
    alca.mouseReleaseEvent(_EventoFalso(QPoint(560, 540)))
    deslocamento = painel_destacado.pos() - posicao_antes
    print("OK: arrastar a barra move a janela destacada:", (deslocamento.x(), deslocamento.y()) == (60, 40))

    # clicar em NSD-2 de novo - deve achar a janela destacada (nao duplicar).
    widget._ticket_clicado(ticket_2)
    print("OK: ainda so 1 janela destacada apos clicar de novo:", len(widget._janelas_destacadas) == 1)

    # abrir NSD-1 no (novo) anexado, com NSD-2 destacado ao mesmo tempo.
    widget._ticket_clicado(ticket_1)
    app.processEvents()
    print("OK: NSD-1 no anexado enquanto NSD-2 continua destacado:",
          widget._painel_anexado.ticket_atual_chave() == "NSD-1" and "NSD-2" in widget._janelas_destacadas)

    # 🔥 regressao do bug relatado com print de tela (2026-08-16): "se eu
    # desfixo um ticket, clico em outro, e volto nesse q esta desfixado, nao
    # e pra ter nenhum fixado... assim que clico em um ticket, apenas o
    # selecionado tem de aparecer" - clicar de novo em NSD-2 (destacado) traz
    # a janela pra frente E fecha o anexado que estava mostrando NSD-1, pra
    # nunca ficar com os dois "selecionados" ao mesmo tempo.
    widget._ticket_clicado(ticket_2)
    app.processEvents()
    print("OK: trazer NSD-2 destacado pra frente fecha o anexado (NSD-1):", not widget._painel_anexado.isVisible())
    print(
        "OK: so NSD-2 aparece selecionado, nao os dois ao mesmo tempo:",
        widget._ticket_esta_aberto("NSD-2") and not widget._ticket_esta_aberto("NSD-1"),
    )

    # reanexar NSD-2 - devolve pro slot anexado (troca NSD-1 por NSD-2 la).
    widget._reanexar(painel_destacado)
    app.processEvents()
    print("OK: NSD-2 saiu de destacado apos reanexar:", "NSD-2" not in widget._janelas_destacadas)
    print("OK: NSD-2 esta de volta no anexado:", widget._painel_anexado.ticket_atual_chave() == "NSD-2")

    # limite de janelas destacadas (configurado como 2 neste teste).
    widget._alternar_destaque(widget._painel_anexado)  # destaca NSD-2 (1/2)
    widget._ticket_clicado(ticket_1)
    app.processEvents()
    widget._alternar_destaque(widget._painel_anexado)  # destaca NSD-1 (2/2)
    print("OK: 2 janelas destacadas, no limite:", len(widget._janelas_destacadas) == 2)

    # 🔥 regressao do bug "tickets se sobrepondo ao selecionar varios" -
    # destacar 2 seguidos SEM arrastar nenhum antes nao pode deixa-los na
    # mesma posicao (cascata, ver PASSO_CASCATA_JANELAS_DESTACADAS).
    posicoes = [(p.x(), p.y()) for p in widget._janelas_destacadas.values()]
    print("OK: janelas destacadas em cascata, nao sobrepostas:", posicoes[0] != posicoes[1])

    # fechar uma janela destacada libera o ticket pro anexado de novo.
    chave_qualquer = next(iter(widget._janelas_destacadas))
    painel_qualquer = widget._janelas_destacadas[chave_qualquer]
    widget._fechar_painel_detalhes(painel_qualquer)
    print("OK: fechar destacada libera o ticket:", chave_qualquer not in widget._janelas_destacadas)

    # fechar a janela principal fecha o anexado, mas NAO as destacadas.
    destacadas_antes = dict(widget._janelas_destacadas)
    widget.close()
    print("OK: anexado escondido ao fechar a janela principal:", not widget._painel_anexado.isVisible())
    print("OK: destacadas sobrevivem ao fechar a janela principal:",
          all(p.isVisible() for p in destacadas_antes.values()))


if __name__ == "__main__":
    main()
