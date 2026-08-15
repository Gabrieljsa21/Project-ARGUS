"""Pontuação de foco (1-100) por ticket - ideia adaptada do
`triagem-inteligente-prototipo` (TechTalk "Triagem Inteligente com IA"), com uma
diferença deliberada: aqui é SÓ pra ordenar/exibir no Argus, NUNCA escreve nada
de volta no Jira (pedido explícito do usuário - o próprio protótipo/deck
recomenda não automatizar antes de medir acerto real, e um heurístico por
palavra-chave erra mais que um modelo de verdade).

Combina 3 fatores, os mesmos da fila dinâmica do protótipo (`Fila/
ChamadoNaFila.cs`/`FilaDinamicaDeAtendimento.cs`), MENOS o de "empresa" (não se
aplica aqui - o Argus mostra os chamados de UMA pessoa só, não uma fila
compartilhada entre vários atendentes de várias empresas):
1. Prioridade real do Jira (base).
2. Urgência mencionada no texto livre (descrição/comentário/imagem) que a
   prioridade não capturou - detectada por palavra-chave, sem LLM (a mesma
   ideia do `ChamadoSimuladoChatClient.cs` do protótipo, que também é um
   stand-in por palavra-chave no lugar de um modelo de verdade).
3. SLA restante de verdade (via Jira Service Management, `/rest/servicedeskapi/
   request/{chave}/sla` - "Time to resolution").
"""

PONTUACAO_BASE_PRIORIDADE = {
    "Lowest": 10,
    "Low": 30,
    "Medium": 50,
    "High": 75,
    "Highest": 95,
}
PONTUACAO_BASE_PADRAO = 50

BONUS_URGENCIA_TEXTO = 20

BONUS_SLA_ESTOURADO = 25
BONUS_SLA_MENOS_1H = 20
BONUS_SLA_MENOS_4H = 10
BONUS_SLA_MENOS_12H = 5

PALAVRAS_URGENCIA = (
    "urgente", "urgência", "urgencia", "crítico", "critico", "emergência", "emergencia",
    "até hoje", "ate hoje", "hoje mesmo", "o quanto antes", "o mais rápido possível",
    "o mais rapido possivel", "imediato", "imediatamente", "agora mesmo",
    "paramos de vender", "parados", "parado", "não conseguimos vender", "nao conseguimos vender",
)


def detectar_urgencia_no_texto(texto: str) -> bool:
    """Heurístico por palavra-chave (sem LLM/dependência nova) - mesmo espírito
    do stand-in usado pelo protótipo original antes de trocar por um `IChatClient`
    de verdade. Fácil de trocar por um classificador melhor depois, sem mudar
    quem chama isso (`JiraProvider`)."""
    texto_normalizado = texto.lower()
    return any(palavra in texto_normalizado for palavra in PALAVRAS_URGENCIA)


def _bonus_sla(sla_info: dict | None) -> int:
    if sla_info is None:
        return 0
    if sla_info.get("breached"):
        return BONUS_SLA_ESTOURADO
    restante_horas = sla_info.get("restante_millis", 0) / 3_600_000
    if restante_horas < 1:
        return BONUS_SLA_MENOS_1H
    if restante_horas < 4:
        return BONUS_SLA_MENOS_4H
    if restante_horas < 12:
        return BONUS_SLA_MENOS_12H
    return 0


def calcular_pontuacao_foco(prioridade: str, urgencia_no_texto: bool, sla_info: dict | None) -> int:
    base = PONTUACAO_BASE_PRIORIDADE.get(prioridade, PONTUACAO_BASE_PADRAO)
    bonus_texto = BONUS_URGENCIA_TEXTO if urgencia_no_texto else 0
    return min(100, base + bonus_texto + _bonus_sla(sla_info))
