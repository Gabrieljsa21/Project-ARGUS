"""Camada de proteção aplicada a QUALQUER texto de ticket (descrição, comentário
ou descrição de imagem via visão) antes de ele passar pela detecção de urgência
(ver `pontuacao.py`) - mesma ideia de `Seguranca/MascaradorDeDadosSensiveis.cs`
do protótipo `triagem-inteligente-prototipo` (TechTalk "Triagem Inteligente com
IA"). Regras propositalmente simples (regex de exemplo, não um detector de PII
de produção) - o ponto é garantir que a camada exista no fluxo antes de
qualquer análise, não entregar uma solução completa de mascaramento."""

import re

_REGRAS = (
    ("senha ou token", re.compile(r"(senha|password|token|bearer)\s*[:=]?\s*\S+", re.IGNORECASE)),
    ("CPF", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("CNPJ", re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")),
    ("cartão de crédito", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
)


def mascarar(texto: str) -> str:
    resultado = texto
    for nome, padrao in _REGRAS:
        resultado = padrao.sub(f"[{nome} removido]", resultado)
    return resultado
