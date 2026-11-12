"""Roda pelo pytest os testes antigos em formato de script (`main()` que
imprime "OK:"/"FALHA:" e devolve o código de saída), cada um no seu processo:
eles criam a própria QApplication, que não pode ser compartilhada entre
arquivos. Falha se o script sair com erro ou imprimir alguma checagem falsa.
Novos testes devem ser escritos direto no estilo pytest (`testar_unidade_*.py`)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PASTA = Path(__file__).parent
RAIZ = PASTA.parent
# Os de unidade já são coletados pelo próprio pytest; os de diagnóstico e o do
# Jira real precisam de tela ou de rede e ficam de fora.
SCRIPTS = sorted(
    p.name for p in PASTA.glob("testar_*.py")
    if p.name not in {"testar_scripts.py", "testar_jira_provider_real.py",
                      "testar_cor_titulo_sla.py", "testar_tooltip_pontuacao.py"}
    and not p.name.startswith("testar_unidade_")
)


@pytest.mark.parametrize("script", SCRIPTS)
def test_script(script):
    ambiente = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(RAIZ), "PYTHONIOENCODING": "utf-8"}
    resultado = subprocess.run(
        [sys.executable, str(PASTA / script)], cwd=RAIZ, env=ambiente,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    saida = resultado.stdout + resultado.stderr
    ruins = [linha for linha in saida.splitlines() if linha.startswith("FALHA") or linha.rstrip().endswith(": False")]
    assert resultado.returncode == 0 and not ruins, saida[-3000:]
