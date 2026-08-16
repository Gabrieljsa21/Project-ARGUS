# Argus — arquitetura consolidada

Widget desktop de notificação de chamados do Jira. Nasceu de uma ideia de notificação visual da GAIA, mas é desenhado desde o início como **projeto separado**, com repo próprio no GitHub pessoal do usuário — usável sozinho por colegas da Nordware que não querem a GAIA inteira (voz, Discord, LLM), e integrável dentro da GAIA como um módulo a mais.

Este documento consolida as decisões tomadas em uma sessão de design (2026-08-14), antes de qualquer linha de código escrita. Não substitui julgamento durante a implementação — decisões pequenas (intervalo exato de polling, cores, nomes de variável) ficam para a hora de codar.

## Estado atual (2026-08-15)

Todas as fases da seção "Fases sugeridas" (fim deste documento) foram
implementadas, além de features que não estavam no design original. Onde
este documento descrevia um PLANO, as seções abaixo foram atualizadas pra
refletir o que existe de verdade; novas seções cobrem o que foi adicionado
depois. Ver `README.md` pro resumo rápido de uso.

## Objetivo

Substituir a notificação de e-mail crua do Jira (assunto + corpo cheio de rodapé da Atlassian) por um widget sempre visível no desktop, que mostra, por status de atendimento, o que precisa da atenção do usuário — sem depender do avatar Live2D/VTube Studio, que é um sistema totalmente separado.

## Escopo

- **Só Jira.** Não cobre e-mail, Documentos, Pagamentos, Pulse, Reuniões (essas ficam com a GAIA, se um dia existirem — fora deste projeto).
- **Só chamados atribuídos ao usuário** (`assignee = currentUser()`). Chamados de melhoria onde o usuário é só reporter/watcher (encaminhados ao Time de Produtos) ficam de fora — não são responsabilidade dele.
- **Público:** colegas da Nordware que usam a mesma instância Jira (`nordwareservices.atlassian.net`), sem querer a GAIA completa.

## Fluxo de status rastreado

Baseado no fluxo real do Jira (Nordware Service Desk, projeto NSD), validado ao vivo via API:

| Status (nome exato no Jira) | Rastreado? |
|---|---|
| Em Revisão | Sim |
| Aguardando atendimento | Sim |
| Aguardando cliente | Sim |
| Aguardando desenvolvimento | Sim |
| Em Andamento | Não (não usado atualmente pelo usuário) |
| Aguardando Terceiros | Não (não usado atualmente) |
| Resolvido | Não (terminal — ticket resolvido não pede ação, some da contagem) |

JQL base: `assignee = currentUser() AND status in ("Em Revisão", "Aguardando atendimento", "Aguardando cliente", "Aguardando desenvolvimento")`.

### Caso especial: "Aguardando desenvolvimento" exige 2 saltos

Quando um chamado do Service Desk entra nesse status, uma automação do Jira cria um ticket **vinculado** no board de dev (ex.: `NSD-12977` → `PLATZ-6624`, vínculo tipo **"Problem/Incident"**, com o rótulo **"is caused by"** do lado do ticket NSD). Os desenvolvedores só comentam no ticket deles, nunca no NSD original.

Consequência pra arquitetura: a categoria "Dev" precisa de **polling em 2 etapas**:
1. Buscar tickets NSD com `status = "Aguardando desenvolvimento"`.
2. Para cada um, ler `issuelinks`, filtrar por `type.name == "Problem/Incident"`, pegar o issue vinculado (`inwardIssue`/`outwardIssue`, dependendo da direção).
3. Checar novidade (comentário, mudança de status) **no ticket vinculado**, não no ticket NSD.

O usuário confirmou que esse tipo de vínculo é sempre o mesmo (a automação nunca varia) — não precisa de lógica adicional para detectar variações.

### SLA — implementado, alimenta a pontuação de foco e o painel de detalhes

Cada issue carrega um campo de SLA nativo do Jira Service Management (no schema atual da instância, `customfield_10100` = "Time to resolution") com `ongoingCycle.remainingTime` (`.millis` e `.friendly`, ex.: "5h 4m"), `breachTime` e `breached` (booleano). Buscado via `/rest/servicedeskapi/request/{chave}/sla` (`JiraProvider._obter_sla_info`) — usado pra:
- **Pontuação de foco** (ver seção própria abaixo) — SLA estourado escala por hora real de atraso.
- **Painel de detalhes** — mostra o texto pronto (`remainingTime.friendly`) como "Time to resolution".

## Regra de "novidade"

Um ticket entra no contador de **novidades** de uma categoria quando, desde a última vez que o usuário abriu aquele ticket especificamente, aconteceu pelo menos um destes eventos:

| Evento | Conta como novidade? |
|---|---|
| Ticket atribuído ao usuário | Sim |
| Cliente comentou | Sim |
| Status mudou | Sim |
| Prioridade mudou | Sim |
| Usuário comentou | Não |
| Comentário automático do Jira ("Automation for Jira", avisos de SLA etc.) | Não |
| Polling rodou e nada mudou | Não |

**O que limpa a novidade:** só abrir o ticket individual (drill-down até o card dele). Abrir a lista da categoria (ver todos os tickets daquele status) **não limpa nada sozinho** — o usuário pode ter 15 tickets ali e não ter lido todos.

Implementação: exige um registro persistido por ticket (chave → timestamp/versão da última vez visto), comparado contra o estado atual do ticket a cada polling — mesmo padrão que `gmail_ultimo_id_visto` já usa na GAIA, adaptado pra granularidade de ticket em vez de e-mail. Precisa de rotina de limpeza (tickets resolvidos há N dias saem do registro).

## Pontuação de foco (implementado, 2026-08-15)

Ideia trazida de `triagem-inteligente-prototipo` (TechTalk "Triagem Inteligente
com IA" do usuário) - decisão explícita: SÓ ordena/exibe a lista, NUNCA
escreve nada de volta no Jira. `argus/pontuacao.py`, `calcular_pontuacao_foco`
(1-100) combina:

1. **Prioridade real do Jira** (base) - Lowest=10, Low=30, Medium=50, High=75,
   Highest=95.
2. **Urgência no texto livre** (descrição + comentário + descrição de print
   anexado via Visão) - heurístico por palavra-chave PT-BR, SEM LLM
   (`detectar_urgencia_no_texto`), ignora negação ("não é urgente"/"sem
   urgência"/"não precisa ser imediato" são removidas do texto ANTES de
   procurar as palavras-chave, não descartam a detecção inteira). +20 se
   confirmada; ganha PISO próprio de 75 - sinal mais confiável que o relógio
   do SLA sozinho, porque é alguém dizendo isso de propósito.
3. **SLA real** ("Time to resolution", ver seção acima) - se estourado,
   escala por HORA REAL de atraso (`BONUS_SLA_ESTOURADO_BASE +
   INCREMENTO_SLA_POR_HORA_ESTOURADA * horas`), sem piso próprio (correção
   2026-08-15: um piso fixo fazia até um SLA estourado há poucos minutos
   numa Lowest pular na frente de um High genuinamente mais crítico - só o
   ACÚMULO de muitas horas de atraso deve reclassificar prioridade, não o
   simples fato de ter estourado).

`argus/seguranca.py` mascara senha/token/CPF/CNPJ/cartão do texto antes de
rodar a detecção de urgência (porte do protótipo C# original).

**Análise de imagem** (`_obter_texto_para_analise`) - quando o ticket tem
print anexado, SEMPRE analisado (não só quando sem descrição escrita) via
gancho opcional `descrever_imagem` (Groq, injetado por quem sobe o widget -
o Argus em si não tem dependência de LLM nenhuma, fica leve/usável pelos
colegas sem chave de IA). Cache por anexo (`chave:id_do_anexo`, não por
ticket) - print novo não reaproveita a análise do anexo antigo.

## Cores de prioridade (implementado, 2026-08-15)

`core/tema.py::CORES_PRIORIDADE` - Highest `#FF5C5C`, High `#FF9F43`, Medium
`#E8C66A`, Low `#73B7FF`, Lowest `#9AA3AD`. Representa a prioridade REAL do
Jira, nunca a pontuação de foco (conceitos diferentes: "o que é formalmente
urgente" vs. "o que focar agora"). Aplicada só no código do ticket
(`[score] CHAVE`, rich text no `QLabel`) - resumo continua na cor normal, sem
repetir o NOME da prioridade por extenso (a legenda das 5 cores, fixa no topo
do painel de tickets, já cobre isso).

## Painel de detalhes + análise via LLM opcional (implementado, 2026-08-15)

Clicar num ticket abre `_PainelDetalhesTicket` - janela flutuante PRÓPRIA (não
embutida na principal) à direita, com Time to resolution, Plataforma, Empresa,
Relator, Responsável, Tipo de solicitação e Status. Campos extras via IDs
confirmados direto contra a instância real (MCP Atlassian, projeto NSD):
`customfield_14901`=Plataforma, `customfield_14601`=Empresa,
`customfield_10007`=objeto de request do JSM (`.requestType.name`=Tipo de
solicitação). Botão "Abrir ticket" cobre o clique direto de antes.

Botão "Analisar" (só aparece se AMBOS `JiraProvider.obter_detalhes_completos`
E um gancho `analisar_ticket` forem injetados - opcional, mesmo espírito do
gancho de Visão): busca descrição + TODOS os comentários sob demanda
(`obter_detalhes_completos`, diferente do polling periódico que só olha o
último comentário pra detectar novidade), deixa adicionar um comentário
extra, roda numa `QThread` própria (não trava a janela), e mostra o rascunho
gerado num dialog revisável/copiável. NUNCA posta no Jira sozinho.

## Otimização: busca 1x, classifica N vezes (implementado, 2026-08-15)

`JiraProvider.buscar_dados_brutos()` isola a parte cara (JQL ×4 + SLA por
ticket + Visão/urgência) SEM comparar contra nenhuma persistência;
`classificar(dados_brutos, persistencia=None)` compara o resultado já
buscado contra qualquer `Persistencia`, sem rede nenhuma. `listar_categorias()`
continua com o mesmo comportamento de sempre por fora (usa as duas peças por
baixo). Motivo: a GAIA passou a comparar o mesmo estado do Jira contra DUAS
persistências por ciclo (fala por voz + lembrete de não-visualizado) - sem
essa separação, isso dobrava as requisições ao Jira por checagem.

## Modelo de interação da UI

Não é uma pilha de widgets (uma bolha por categoria) — é **um widget só**, com uma barra de contadores por categoria embaixo da personagem (opcional, ver abaixo).

- **Dois modos de contagem**, alternados clicando na personagem (sem arrastar):
  - **Novidades** — conta só o que mudou desde a última vez visto, por categoria. Categoria sem novidade nenhuma **some da barra** (não aparece com "0").
  - **Total** — conta quantos tickets existem agora em cada status, independente de novidade. Categoria com total zero também some.
  - Categorias com pelo menos uma novidade ganham um `*` — em **ambos** os modos, não só no de novidades (trocar pra "total" não esconde que tem algo novo esperando).
- **Clicar num número/categoria específico** (não na personagem) abre a lista de tickets daquela categoria — mostrando o "novo" com marcação visual e o resto sem.
- **Clicar num ticket da lista** abre o card com detalhes (código, título, prioridade, tempo aguardando, link "Abrir no Jira") e é o que **limpa** a novidade daquele ticket.
- Navegação entre níveis (barra → lista de categoria → detalhe do ticket) é navegação de CONTEÚDO dentro do mesmo card/janela expandida (com "voltar"), não uma nova animação de crescimento a cada nível — só compacto ⇄ expandido anima geometria.

## Janela (comportamento de desktop)

Réplica das regras de janela que o modelo 2D do VTube Studio já tem — **exceto zoom/redimensionar**, dispensado explicitamente:

- Transparência real (alpha), não chroma-key.
- Sempre no topo de todas as janelas.
- Sem borda, sem entrada na barra de tarefas/Alt-Tab.
- Clique-através nas áreas transparentes — só a silhueta visível (personagem + barra) é clicável, via máscara de alpha (`setMask`).
- **Arrastável** — clicar e mover reposiciona o widget. Precisa diferenciar clique (toggle novidades/total) de arraste (reposicionar) por um limiar pequeno de movimento entre mouse-down e mouse-up.
- **Posição persiste** entre reinícios (salva em config, não reseta pro padrão a cada abertura).

## Personagem/ícone — opcional e decorativo (implementado como ÍCONE ESTÁTICO, não animação)

`_Alavanca` (placeholder original) hoje desenha o ícone oficial do Argus (pavão
de cristal, `assets/icone_argus.png`) - clique alterna novidades/total,
arrastar move a janela, igual ao design original. **Decisão real** (2026-08-15,
diferente do plano abaixo): ficou estático - sem animação Entrada/Idle/Hover,
sem WebP - simplicidade suficiente pro propósito (indicar visualmente que algo
mudou), sem o custo de implementar/manter frames de animação. Continua
decorativo/opcional - o MVP funciona 100% só com a barra de contadores.

## Arquitetura de módulo

```
argus/
├── core/                  # janela, estado (novidades/total/lista/detalhe), drag/transparência/
│                          # click-through, animação opcional — não sabe o que é Jira
├── providers/
│   └── jira_provider.py  # implementa NotificacaoProvider usando a JQL/issuelinks validados
├── persistencia.py        # interface abstrata p/ "visto" por ticket + posição da janela
└── app.py                 # entrypoint standalone — própria QApplication, config via .env
```

Dois contratos garantem que funciona sozinho E dentro da GAIA:

- **`NotificacaoProvider`** — contrato mínimo (`providers/base.py`): `listar_categorias()` (devolve `list[Categoria]` já com `novo` calculado) e `marcar_visto(chave_ticket)`. O `core/` só fala com essa interface. `JiraProvider` expõe métodos EXTRA (`buscar_dados_brutos()`/`classificar()`/`obter_detalhes_completos()`, ver seções abaixo) que não fazem parte do contrato — opcionais, checados via `getattr` por quem consome (ex.: `ArgusWidget`), pra um provider mínimo (ou uma fonte diferente de Jira) continuar funcionando sem eles.
- **`Persistencia`** — abstrai onde salva "visto"/posição. Rodando sozinho: arquivo próprio (ex. `~/.argus/config.json`). Rodando na GAIA: implementação que grava no `brain.json` dela.

## Distribuição

- **Repo próprio no GitHub pessoal do usuário** (não dentro do repo privado `Project-GAIA`/`assistant`, que colegas não conseguem acessar).
- GAIA consome o Argus como **dependência** (`pip install git+https://github.com/.../argus.git` ou submódulo git) — nunca código colado/duplicado.
- Cada colega configura sua própria credencial (Basic Auth: e-mail + API token do Jira, gerado em `id.atlassian.com/manage-profile/security/api-tokens`) — mesma instância Jira, credencial individual.

## Tecnologia

- **PySide6** — mesma stack já usada em toda a GAIA (`ui/qt_painel.py` e módulos). Janela `Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`, `WA_TranslucentBackground`.
- Rodando dentro da GAIA: instanciado na MESMA `QApplication` do Painel — nunca um segundo runtime Qt.
- Polling simples (loop assíncrono, como os já existentes na GAIA pra e-mail/preço de hardware) — não webhook (exigiria expor endpoint público, infraestrutura desnecessária pra esse caso de uso).

## Fases sugeridas (todas concluídas, ver "Estado atual" no topo)

1. ✅ **Motor + dado, sem personagem**: barra de contadores, dois modos, lista de categoria, card de ticket, provider Jira com os 4 status + o vínculo de 2 saltos, persistência de "visto".
2. ✅ Validar clique-através/arrastar/transparência num protótipo trivial antes de investir em polimento visual.
3. ✅ Empacotar como projeto instalável (repo próprio, `pyproject.toml`, instruções de config de credencial).
4. ✅ Integrar na GAIA (`run.py` instancia o `JiraProvider` num loop próprio pra voz; `ui/qt_painel.py` instancia o `ArgusWidget` na MESMA `QApplication` do Painel, com adaptador de persistência pro `brain.json`).
5. ✅ Personagem virou ÍCONE ESTÁTICO (pavão de cristal), não animação - ver seção "Personagem/ícone" acima; decisão consciente de simplicidade, não uma etapa pulada.

Trabalho depois destas 5 fases (não previsto no design original, ver seções
próprias acima): pontuação de foco + mascaramento + análise de imagem, cores
de prioridade, painel de detalhes + análise via LLM, otimização de
busca/classificação.
