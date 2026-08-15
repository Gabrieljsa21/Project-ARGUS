"""Validação manual contra o Jira DE VERDADE (lê .env) - não faz parte do
pacote. Só imprime chave/resumo/status/novo de cada ticket, nunca credencial."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from argus.persistencia import PersistenciaArquivo
from argus.providers.jira_provider import JiraProvider

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

persistencia = PersistenciaArquivo(os.path.join(os.path.dirname(__file__), "_config_teste_real.json"))
provider = JiraProvider(
    os.environ["JIRA_BASE_URL"],
    os.environ["JIRA_EMAIL"],
    os.environ["JIRA_API_TOKEN"],
    persistencia,
)

categorias = provider.listar_categorias()
for categoria in categorias:
    print(f"\n=== {categoria.nome_exibicao} - novidades: {categoria.novidades} / total: {categoria.total} ===")
    for ticket in categoria.tickets:
        marca = " [NOVO]" if ticket.novo else ""
        print(f"  {ticket.chave} | {ticket.status} | {ticket.prioridade} | {ticket.resumo}{marca}")
