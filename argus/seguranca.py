"""Camada de proteção aplicada a QUALQUER texto de ticket (descrição, comentário
ou descrição de imagem via visão) antes de ele passar pela detecção de urgência
(ver `pontuacao.py`) - mesma ideia de `Seguranca/MascaradorDeDadosSensiveis.cs`
do protótipo `triagem-inteligente-prototipo` (TechTalk "Triagem Inteligente com
IA"). Regras propositalmente simples (regex de exemplo, não um detector de PII
de produção) - o ponto é garantir que a camada exista no fluxo antes de
qualquer análise, não entregar uma solução completa de mascaramento."""

import re

# 🔥 Senha/token só com separador (2026-11-12): antes o `:`/`=` era opcional
# e "senha errada" ou "token expirou" perdiam a palavra seguinte, mudando o
# sentido do texto. Agora exige "senha: x"/"token=x", ou "Bearer <valor longo>".
_REGRAS = (
    ("senha ou token", re.compile(r"\b(senha|password|token|api[ _-]?key|secret)\s*[:=]\s*\S+", re.IGNORECASE)),
    ("senha ou token", re.compile(r"\bbearer\s+[A-Za-z0-9._~+/-]{12,}=*", re.IGNORECASE)),
    ("CPF", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("CNPJ", re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")),
    ("cartão de crédito", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
)


def mascarar(texto: str) -> str:
    resultado = texto
    for nome, padrao in _REGRAS:
        resultado = padrao.sub(f"[{nome} removido]", resultado)
    return resultado
