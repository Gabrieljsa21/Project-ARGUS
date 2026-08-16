# Argus — arquitetura consolidada

Widget desktop de notificação de chamados do Jira. Nasceu de uma ideia de notificação visual da GAIA, mas é desenhado desde o início como **projeto separado**, com repo próprio no GitHub pessoal do usuário — usável sozinho por colegas da Nordware que não querem a GAIA inteira (voz, Discord, LLM), e integrável dentro da GAIA como um módulo a mais.

Este documento consolida as decisões tomadas em uma sessão de design (2026-08-14), antes de qualquer linha de código escrita. Não substitui julgamento durante a implementação — decisões pequenas (intervalo exato de polling, cores, nomes de variável) ficam para a hora de codar.

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

### SLA disponível (não usado ainda, mas confirmado disponível)

Cada issue carrega um campo de SLA nativo do Jira Service Management (no schema atual da instância, `customfield_10100` = "Time to resolution") com `ongoingCycle.remainingTime`, `breachTime` e `breached` (booleano). Estruturado, não precisa ser inferido de texto — útil se algum dia quisermos mostrar "tempo restante" no card do ticket.

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

## Personagem/animação — opcional e decorativa

A arte animada da Galateia (Entrada/Idle/Hover) **não é núcleo funcional** — é só um indicador visual acima da barra, usado para chamar atenção de que algo mudou. Isso significa:

- O MVP pode (e deve) nascer **sem nenhuma animação** — só a barra de contadores já é o produto completo e funcional.
- Adicionar a personagem depois é estritamente aditivo, nunca bloqueante.
- Se/quando implementada: WebP animado com alpha real, decodificado uma vez em `QPixmap`, sem Chromium/Rive/Lottie (custo de RAM incompatível com rodar ao lado de STT/LLM/TTS na mesma máquina). Ver seção de tecnologia.

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

- **`NotificacaoProvider`** — `listar_categorias()`, `buscar_novidades()`, `marcar_visto(ticket_id)`. O `core/` só fala com essa interface. Uma fonte nova (outro Jira, outro sistema) implementa a mesma interface sem tocar no motor do widget.
- **`Persistencia`** — abstrai onde salva "visto"/posição. Rodando sozinho: arquivo próprio (ex. `~/.argus/config.json`). Rodando na GAIA: implementação que grava no `brain.json` dela.

## Distribuição

- **Repo próprio no GitHub pessoal do usuário** (não dentro do repo privado `Project-GAIA`/`assistant`, que colegas não conseguem acessar).
- GAIA consome o Argus como **dependência** (`pip install git+https://github.com/.../argus.git` ou submódulo git) — nunca código colado/duplicado.
- Cada colega configura sua própria credencial (Basic Auth: e-mail + API token do Jira, gerado em `id.atlassian.com/manage-profile/security/api-tokens`) — mesma instância Jira, credencial individual.

## Tecnologia

- **PySide6** — mesma stack já usada em toda a GAIA (`ui/qt_painel.py` e módulos). Janela `Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`, `WA_TranslucentBackground`.
- Rodando dentro da GAIA: instanciado na MESMA `QApplication` do Painel — nunca um segundo runtime Qt.
- Polling simples (loop assíncrono, como os já existentes na GAIA pra e-mail/preço de hardware) — não webhook (exigiria expor endpoint público, infraestrutura desnecessária pra esse caso de uso).

## Fases sugeridas

1. **Motor + dado, sem personagem**: barra de contadores, dois modos, lista de categoria, card de ticket, provider Jira com os 4 status + o vínculo de 2 saltos, persistência de "visto".
2. Validar clique-através/arrastar/transparência num protótipo trivial antes de investir em polimento visual.
3. Empacotar como projeto instalável (repo próprio, `pyproject.toml`, instruções de config de credencial).
4. Integrar na GAIA (`run.py` instancia dentro da `QApplication` existente, com adaptador de persistência pro `brain.json`).
5. Personagem/animação como fase adicional, opcional, sem tocar no que já roda.
