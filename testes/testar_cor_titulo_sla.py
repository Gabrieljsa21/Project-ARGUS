"""Valida a cor do título (resumo) por faixa de SLA e o sufixo de horas
concatenado nele (2026-08-28, pedido do usuário: "faz a cor da fonte ser
com base na SLA, coloca vermelho p as estouradas, laranja faltando 1h,
amarelo 2h" + "pode ate concatenar no final do titulo o time to
resolution, mas apenas horas, ignore minutos")."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel

from argus.core.tema import TEXT_COLOR, TEXT_DIM, CORES_PRIORIDADE
from argus.core.widget import _LinhaTicket, _cor_titulo_por_sla, _sufixo_sla
from argus.modelos import Ticket


def _ticket(sla_estourado=False, sla_restante_millis=None, novo=False):
    return Ticket(
        chave="TCK-1",
        resumo="Exemplo",
        status="Aguardando Atendimento",
        prioridade="Medium",
        url="https://jira.example/TCK-1",
        atualizado_em="2026-08-28T12:00:00.000+0000",
        novo=novo,
        sla_estourado=sla_estourado,
        sla_restante_millis=sla_restante_millis,
    )


class CorTituloPorSlaTest(unittest.TestCase):
    def test_sem_sla_mantem_cor_padrao(self):
        self.assertEqual(TEXT_DIM, _cor_titulo_por_sla(_ticket(), TEXT_DIM))

    def test_estourado_e_sempre_vermelho_mesmo_com_muito_tempo_restante_no_campo(self):
        cor = _cor_titulo_por_sla(_ticket(sla_estourado=True, sla_restante_millis=-1), TEXT_DIM)
        self.assertEqual(CORES_PRIORIDADE["Highest"], cor)

    def test_faltando_menos_de_1h_e_laranja(self):
        cor = _cor_titulo_por_sla(_ticket(sla_restante_millis=30 * 60 * 1000), TEXT_DIM)
        self.assertEqual(CORES_PRIORIDADE["High"], cor)

    def test_faltando_entre_1h_e_2h_e_amarelo(self):
        cor = _cor_titulo_por_sla(_ticket(sla_restante_millis=int(1.5 * 3_600_000)), TEXT_DIM)
        self.assertEqual(CORES_PRIORIDADE["Medium"], cor)

    def test_faltando_2h_ou_mais_mantem_cor_padrao(self):
        cor = _cor_titulo_por_sla(_ticket(sla_restante_millis=3 * 3_600_000), TEXT_COLOR)
        self.assertEqual(TEXT_COLOR, cor)

    def test_limite_exato_de_1h_ainda_conta_como_dentro_da_faixa_amarela(self):
        # 🔥 `< 1`/`< 2`, não `<=` (mesmo critério de `pontuacao._bonus_sla`)
        # - exatamente 1h restante já NÃO é mais "faltando 1h" (laranja), é
        # a faixa de 2h (amarelo).
        cor = _cor_titulo_por_sla(_ticket(sla_restante_millis=1 * 3_600_000), TEXT_DIM)
        self.assertEqual(CORES_PRIORIDADE["Medium"], cor)


class SufixoSlaTest(unittest.TestCase):
    def test_sem_sla_nao_gera_sufixo(self):
        self.assertEqual("", _sufixo_sla(_ticket()))

    def test_ignora_minutos_arredondando_pra_baixo(self):
        # 3h59m -> "3h", nunca "4h" nem "3h59m"
        millis = 3 * 3_600_000 + 59 * 60_000
        self.assertEqual(" · SLA em 3h", _sufixo_sla(_ticket(sla_restante_millis=millis)))

    def test_estourado_mostra_horas_de_atraso_em_valor_absoluto(self):
        sufixo = _sufixo_sla(_ticket(sla_estourado=True, sla_restante_millis=-5 * 3_600_000))
        self.assertEqual(" · SLA estourado há 5h", sufixo)

    def test_estourado_ha_menos_de_1h_nao_mostra_0h(self):
        sufixo = _sufixo_sla(_ticket(sla_estourado=True, sla_restante_millis=-10 * 60_000))
        self.assertEqual(" · SLA estourado agora", sufixo)


class ResumoNaLinhaTicketTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _estilo_resumo(self, ticket):
        """Devolve a STRING do estilo (não o widget) - `linha.close()` tira a
        última referência Python da `_LinhaTicket`, e sem ela o objeto C++
        do PySide (widget + filhos) pode ser destruído antes do teste ler
        `styleSheet()` de volta."""
        linha = _LinhaTicket(ticket, "Resumo", QFont(), lambda t: None)
        linha.show()
        self.app.processEvents()
        rotulos = [r for r in linha.findChildren(QLabel) if r.objectName() != "pontuacao_foco"]
        # prefixo (chave) + resumo, nessa ordem de inserção no layout
        estilo = rotulos[-1].styleSheet()
        linha.close()
        return estilo

    def test_resumo_estourado_fica_vermelho(self):
        estilo = self._estilo_resumo(_ticket(sla_estourado=True, sla_restante_millis=-3_600_000))
        self.assertIn(CORES_PRIORIDADE["Highest"], estilo)

    def test_resumo_sem_sla_continua_na_cor_de_novo_lido_de_sempre(self):
        estilo_lido = self._estilo_resumo(_ticket(novo=False))
        estilo_novo = self._estilo_resumo(_ticket(novo=True))
        self.assertIn(TEXT_DIM, estilo_lido)
        self.assertIn(TEXT_COLOR, estilo_novo)


if __name__ == "__main__":
    unittest.main()
