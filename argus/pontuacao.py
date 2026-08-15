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
# 🔥 Piso pra urgência CONFIRMADA no texto (2026-08-15, pedido do usuário:
# "quando eles falam que é urgente, normalmente é bem urgente mesmo, coisa de
# resolver em poucas horas") - diferente do piso de SLA (removido, ver
# `_bonus_sla` abaixo), esse sinal vem de alguém dizendo isso de propósito, não
# só o relógio correndo - garante que um Lowest/Low com urgência real
# confirmada no texto nunca fica pontuando abaixo de um High. Só vale se
# `detectar_urgencia_no_texto` não achou negação (ver `_remover_negacoes`).
PISO_PONTUACAO_URGENCIA_TEXTO = 75

# 🔥 Escalonamento por horas estouradas (2026-08-15, pedido do usuário: "um
# ticket com prioridade baixa que já está com 20h negativas" ficava ATRÁS de
# um High recém-aberto e não urgente, porque o bônus de SLA estourado era
# fixo/+25, não importava há quanto tempo estourou) - cresce com
# `INCREMENTO_SLA_POR_HORA_ESTOURADA` por hora de atraso REAL (`remainingTime.
# millis` negativo = quanto estourou, ver `_obter_sla_info` em
# jira_provider.py).
#
# 🔥 SEM piso pro SLA em si (2026-08-15, correção depois de testar o piso de
# 85: "independente de estar estourado o SLA ou não, algo mais crítico, como
# pedidos não integrando, é muito mais urgente" que uma requisição Lowest tipo
# relatório) - um piso fixo faria QUALQUER SLA estourado (mesmo há poucos
# minutos, numa Lowest) pular na frente de um High genuinamente mais crítico.
# Só o acúmulo de MUITAS horas estouradas consegue empurrar uma prioridade
# baixa pra cima de uma alta, não o simples fato de ter estourado.
BONUS_SLA_ESTOURADO_BASE = 25
INCREMENTO_SLA_POR_HORA_ESTOURADA = 2
BONUS_SLA_MENOS_1H = 20
BONUS_SLA_MENOS_4H = 10
BONUS_SLA_MENOS_12H = 5

PALAVRAS_URGENCIA = (
    "urgente", "urgência", "urgencia", "crítico", "critico", "emergência", "emergencia",
    "até hoje", "ate hoje", "hoje mesmo", "o quanto antes", "o mais rápido possível",
    "o mais rapido possivel", "imediato", "imediatamente", "agora mesmo",
    "paramos de vender", "parados", "parado", "não conseguimos vender", "nao conseguimos vender",
)

# 🔥 Negação (2026-08-15, achado real: "não é urgente" contém a substring
# "urgente" e era classificado como urgente - o oposto do que o texto diz) -
# REMOVE o trecho negado do texto antes de procurar `PALAVRAS_URGENCIA`, em vez
# de descartar a detecção inteira, pra não perder um sinal de urgência
# genuíno em outra parte do mesmo texto (ex.: "não é urgente, mas paramos de
# vender" ainda precisa contar como urgente por causa da segunda parte).
FRASES_NEGACAO_URGENCIA = (
    "não é urgente", "nao e urgente", "não urgente", "nao urgente",
    "sem urgência", "sem urgencia",
    "não precisa ser imediato", "nao precisa ser imediato",
    "não é crítico", "nao e critico", "não crítico", "nao critico",
    "sem pressa",
)


def detectar_urgencia_no_texto(texto: str) -> bool:
    """Heurístico por palavra-chave (sem LLM/dependência nova) - mesmo espírito
    do stand-in usado pelo protótipo original antes de trocar por um `IChatClient`
    de verdade. Fácil de trocar por um classificador melhor depois, sem mudar
    quem chama isso (`JiraProvider`)."""
    texto_normalizado = texto.lower()
    for frase in FRASES_NEGACAO_URGENCIA:
        texto_normalizado = texto_normalizado.replace(frase, "")
    return any(palavra in texto_normalizado for palavra in PALAVRAS_URGENCIA)


def _bonus_sla(sla_info: dict | None) -> int:
    if sla_info is None:
        return 0
    restante_millis = sla_info.get("restante_millis", 0)
    if sla_info.get("breached"):
        # `restante_millis` vem NEGATIVO quando estourado (ex.: -20h em millis)
        # - negar dá quanto tempo passou do prazo, não só que passou.
        horas_estouradas = max(0, -restante_millis) / 3_600_000
        return round(BONUS_SLA_ESTOURADO_BASE + horas_estouradas * INCREMENTO_SLA_POR_HORA_ESTOURADA)
    restante_horas = restante_millis / 3_600_000
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
    pontuacao = base + bonus_texto + _bonus_sla(sla_info)
    if urgencia_no_texto:
        pontuacao = max(pontuacao, PISO_PONTUACAO_URGENCIA_TEXTO)
    return min(100, pontuacao)
