"""Valida o detalhamento e o alvo exclusivo do tooltip da pontuação."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from argus.core.widget import _LinhaTicket
from argus.modelos import Ticket
from argus.pontuacao import calcular_detalhamento_pontuacao
from argus.providers.jira_provider import JiraProvider  # noqa: F401 - valida o consumidor do detalhamento


class TooltipPontuacaoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _ticket(self, detalhes):
        return Ticket(
            chave="TCK-123",
            resumo="Exemplo",
            status="Aguardando Atendimento",
            prioridade=detalhes.prioridade,
            url="https://jira.example/TCK-123",
            atualizado_em="2026-08-25T12:00:00.000+0000",
            pontuacao_foco=detalhes.total,
            detalhamento_pontuacao=detalhes,
        )

    def test_detalhamento_expoe_componentes_e_teto(self):
        detalhes = calcular_detalhamento_pontuacao(
            "Highest", True, {"breached": False, "restante_millis": 30 * 60 * 1000},
        )

        self.assertEqual(95, detalhes.pontos_prioridade)
        self.assertEqual(20, detalhes.bonus_urgencia)
        self.assertEqual(20, detalhes.bonus_sla)
        self.assertFalse(detalhes.sla_estourado)
        self.assertEqual(100, detalhes.total)
        self.assertEqual(100, detalhes.limite)
        self.assertTrue(detalhes.teto_aplicado)

    def test_detalhamento_informa_piso_quando_ele_altera_total(self):
        detalhes = calcular_detalhamento_pontuacao("Low", True, None)

        self.assertEqual(75, detalhes.total)
        self.assertEqual(75, detalhes.piso_urgencia_aplicado)
        self.assertFalse(detalhes.teto_aplicado)

    def test_detalhamento_nao_marca_teto_quando_nao_e_o_limite_real(self):
        detalhes = calcular_detalhamento_pontuacao("High", False, None)

        self.assertEqual(75, detalhes.total)
        self.assertFalse(detalhes.teto_aplicado)

    def test_detalhamento_identifica_sla_estourado(self):
        detalhes = calcular_detalhamento_pontuacao(
            "Medium", False, {"breached": True, "restante_millis": -3 * 3_600_000},
        )

        self.assertTrue(detalhes.sla_estourado)
        self.assertEqual(31, detalhes.bonus_sla)

    def test_tooltip_existe_somente_no_rotulo_do_numero(self):
        detalhes = calcular_detalhamento_pontuacao("High", True, None)
        cliques = []
        linha = _LinhaTicket(self._ticket(detalhes), "Resumo", QFont(), cliques.append)
        linha.show()
        self.app.processEvents()

        rotulo_pontuacao = linha.findChild(QLabel, "pontuacao_foco")
        self.assertIsNotNone(rotulo_pontuacao)
        self.assertEqual("[95]", rotulo_pontuacao.text())
        self.assertIn("Pontuação de foco: 95", rotulo_pontuacao.toolTip())
        self.assertIn("Prioridade High: 75 pontos", rotulo_pontuacao.toolTip())
        self.assertIn("Urgência detectada no texto: +20", rotulo_pontuacao.toolTip())
        self.assertIn("SLA restante: +0", rotulo_pontuacao.toolTip())
        self.assertNotIn("Limite aplicado", rotulo_pontuacao.toolTip())
        self.assertEqual("", linha.toolTip())
        for rotulo in linha.findChildren(QLabel):
            if rotulo is not rotulo_pontuacao:
                self.assertEqual("", rotulo.toolTip())

        QTest.mouseClick(rotulo_pontuacao, Qt.LeftButton)
        self.assertEqual([linha._ticket], cliques)
        linha.close()

    def test_tooltip_usa_rotulo_de_sla_estourado_e_mostra_limite_quando_binding(self):
        detalhes = calcular_detalhamento_pontuacao(
            "Highest", True, {"breached": True, "restante_millis": -10 * 3_600_000},
        )
        linha = _LinhaTicket(self._ticket(detalhes), "Resumo", QFont(), lambda t: None)
        linha.show()
        self.app.processEvents()

        rotulo_pontuacao = linha.findChild(QLabel, "pontuacao_foco")
        tooltip = rotulo_pontuacao.toolTip()
        self.assertIn("SLA estourado: +45", tooltip)
        self.assertNotIn("SLA restante", tooltip)
        self.assertIn("Limite aplicado: 100", tooltip)
        linha.close()


if __name__ == "__main__":
    unittest.main()
