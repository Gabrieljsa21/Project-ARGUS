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

### Exceção: status mudado pelo próprio usuário (2026-08-21)

Pedido do usuário: "quando a mudança for apenas de status realizada por mim, não precisa notificar como novo, apenas atualizar o ticket para a coluna nova" — mudar o status de um chamado ele mesmo (pelo Jira direto) não é "novidade" pra ele mesmo revisar depois; o ticket só precisa refletir a coluna/categoria nova, sem badge "NOVO" nem aviso de voz.

`JiraProvider._classificar_evento` só sabe COMPARAR status (antigo vs. atual) — pra saber QUEM mudou, `_autor_ultima_mudanca_status` busca o changelog do issue (`GET /rest/api/3/issue/{chave}?expand=changelog`, percorrido de trás pra frente até achar o item mais recente com `field == "status"`) e compara o `accountId` do autor contra `self._minha_account_id`. Só chamado quando o status REALMENTE mudou desde o último `visto` (evento raro) — não pesa no polling normal, diferente do SLA/pontuação de foco que rodam pra todo ticket a cada ciclo.

Pro vínculo de 2 saltos ("Aguardando desenvolvimento"), o changelog é consultado no MESMO issue usado pra novidade (o ticket vinculado de dev, não o NSD original) — por isso `_estado_atual` agora guarda também a `chave` do issue que gerou aquele estado, não só os campos comparados.

A checagem de autor só suprime o tipo de evento `"status_mudou"` — se a MESMA atualização também trouxe outro evento (prioridade crítica, reatribuição, comentário de terceiro), esse outro evento ainda conta como novidade normalmente.

## Pontuação de foco (implementado, 2026-08-15)

O número exibido entre colchetes na lista é também o único alvo do tooltip de
explicabilidade: ao passar o mouse diretamente sobre `[pontuação]`, o Argus
mostra a base correspondente à prioridade real, os bônus de urgência e SLA,
eventual piso por urgência e o teto de 100. O detalhamento é produzido junto
do cálculo, em vez de ser reconstruído pela interface, para que o valor exibido
e sua explicação nunca usem regras diferentes. Nenhuma outra parte da linha
abre esse tooltip.

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

## Tooltip fora da paleta (corrigido, 2026-08-26)

Todo `setToolTip()` do Argus (pontuação de foco, "Arrastar", botões de ícone,
código clicável do ticket) renderizava com o preto padrão do Qt - nenhum
deles estiliza o `QToolTip` individualmente, e o `aplicar_estilo_global`
(`core/tema.py`) nunca tinha uma regra pra isso. Corrigido com UMA regra
`QToolTip` global (`SURFACE_COLOR`/`TEXT_COLOR`/`BORDA_SUTIL`, mesmo trio já
usado em inputs/popups do resto do app) - cobre todos os tooltips de uma vez,
não precisa estilizar cada widget individualmente.

## Painel de detalhes: anexado/destacado + análise via LLM opcional (2026-08-15)

Clicar num ticket abre `_PainelDetalhesTicket`, com Time to resolution,
Plataforma, Empresa, Relator, Responsável, Tipo de solicitação e Status.
Campos extras via IDs confirmados direto contra a instância real (MCP
Atlassian, projeto NSD): `customfield_14901`=Plataforma,
`customfield_14601`=Empresa, `customfield_10007`=objeto de request do JSM
(`.requestType.name`=Tipo de solicitação).

**Reescrito (2026-08-15, pedido registrado em `argus_painel_detalhes_ticket.md`)**
pra funcionar como extensão visual do Argus, não uma janela desconectada -
**e simplificado de novo em 2026-08-16** depois que a primeira versão
(reaproveitar uma instância com crossfade animado entre tickets) se mostrou
frágil em uso real: o usuário relatou "tickets se sobrepondo" e "não troca
quando seleciono outro" mesmo após uma tentativa de correção - só validada
por chamada síncrona em teste automatizado, nunca pela animação de verdade
rodando no loop de eventos real. Pedido explícito do usuário: "é p ser
simples, clicou no ticket apareceu ele do lado, clicou em outro ticket, some
o anterior e abre o novo" - e desconsiderar a ideia de lembrar posição entre
sessões se essa fosse a causa. O modelo atual (bem mais simples) é:

- **Anexado (padrão):** cada clique num ticket FECHA a instância de
  `_PainelDetalhesTicket` atualmente anexada (se houver) e ABRE uma
  instância NOVA do zero pro ticket clicado (`ArgusWidget._ticket_clicado`)
  - sem crossfade, sem animação de entrada, sem reaproveitamento. Abre à
  direita da janela principal (ou à esquerda se não couber na área útil do
  monitor atual, recalculado também quando o Argus muda de monitor, ver
  `ArgusWidget.moveEvent`/`_calcular_lado_e_x`). O ticket aberto fica
  destacado na lista (`_LinhaTicket.definir_selecionado`), atualizado na
  hora (nada de esperar animação/polling).
- **Destacar/Reanexar:** ação "Destacar" transforma a instância ATUAL numa
  janela independente, presa àquele ticket até ser reanexada ou fechada; o
  Argus cria uma instância nova/vazia pro slot anexado. Arrastável via uma
  pequena BARRA CENTRALIZADA no cabeçalho (`_AlcaArraste`, ver "Ações
  rápidas" abaixo) - **sem redimensionar** (2026-08-16, pedido do usuário:
  "não preciso do botão redimensionar, usar ele está duplicando botões" - o
  grip de redimensionar foi removido; tamanho fica fixo no valor calculado
  ao destacar). "Reanexar"
  fecha a janela independente e reabre o ticket no slot anexado (reaproveita
  o mesmo caminho de `_ticket_clicado`). Sem memória de posição entre
  sessões (2026-08-16, pedido do usuário - ver acima): cada nova janela
  destacada parte da posição atual do painel anexado, só com uma cascata
  (`PASSO_CASCATA_JANELAS_DESTACADAS` × quantas já estão abertas) pra não
  nascerem empilhadas.
- **Controle de instâncias:** cada ticket tem no máximo UMA instância aberta
  (`ArgusWidget._ticket_clicado` checa `_janelas_destacadas` antes do slot
  anexado) - nunca duas janelas pro mesmo ticket. Clicar num ticket já
  destacado traz a janela pra frente e dispara um pulso de atenção na borda/
  glow (`_PainelDetalhesTicket.trazer_para_frente_com_atencao`); uma
  chacoalhada lateral existe como efeito opcional, ligável no menu de
  Configurações (ver seção própria abaixo).
- **Só um ticket "selecionado" por vez (correção 2026-08-16, bug relatado
  pelo usuário com print de tela):** destacar um ticket, clicar em outro (que
  abre no anexado) e depois voltar no primeiro (destacado) trazia a janela
  destacada pra frente mas deixava o painel ANEXADO aberto também - dois
  tickets apareciam "selecionados" (destacados na lista) ao mesmo tempo.
  Corrigido: `ArgusWidget._fechar_anexado_se_visivel()` fecha o slot anexado
  sempre que uma janela DESTACADA é trazida pra frente - só ele, que
  representa a "seleção implícita"; outras janelas destacadas (tickets
  destacados de propósito) continuam existindo normalmente.
- **Limite de janelas destacadas:** configurável (`.env` como padrão de
  fábrica, ajustável em tempo real no menu de Configurações) - ao atingir o
  limite, `_DialogoAvisoLimite` (dialog próprio, não `QMessageBox` nativo)
  avisa em vez de deixar destacar.
- **Fechamento:** fechar a janela principal fecha o painel ANEXADO junto
  (`ArgusWidget.closeEvent`); janelas DESTACADAS sobrevivem e continuam
  independentes (todas as instâncias de `_PainelDetalhesTicket` são
  top-level SEM parent Qt, mesmo enquanto anexadas - o `ArgusWidget` controla
  o ciclo de vida explicitamente em vez de depender do Qt destruir filhos
  junto com o pai).
- **Tamanho/rolagem:** altura acompanha o conteúdo até o limite da área útil
  do monitor - passado isso, rolagem interna nos campos (mesmo padrão já
  usado pra lista de tickets grande, só cria `QScrollArea` quando REALMENTE
  precisa, ver comentário sobre o bug de encolhimento em `_preencher_painel`).
  Atualização de dados (polling) empurra os campos atualizados pro painel
  aberto (anexado ou destacado) sem recriar a janela
  (`_PainelDetalhesTicket.atualizar_se_mostrando`).
- **Ações rápidas:** botão "Abrir" (Jira) e "Analisar" na linha debaixo do
  conteúdo; no CABEÇALHO (2026-08-16, ajuste de posição pedido pelo usuário):
  🔗 Copiar link colado no código do ticket, à ESQUERDA; à direita, junto do
  ✕ Fechar, o ícone de alfinete 📌 (Destacar/Reanexar) ao lado de ⟳
  Atualizar. **Barra de arraste ACIMA da linha de botões, SEMPRE presente**
  (2026-08-16, ajustado em 2 pedidos do usuário: "quero que ela fique acima
  dos botões" - antes ficava centralizada NA MESMA linha, entre os dois
  grupos de ícones; depois "pode deixar a barra sempre presente, só que
  clicar nela sem desfixar move tudo" - deixou de existir só em modo
  destacado, agora aparece e arrasta a janela em QUALQUER estado, sem
  precisar destacar primeiro, ver `_AlcaArraste`). **Arraste VINCULADO em
  modo anexado** (2026-08-16, pedido do usuário: "a barra de arraste, qnd
  estiver vinculada a barra dos status, tem q mover TUDO, a barra dos
  status tbm") - enquanto anexado, arrastar a barra move a janela
  PRINCIPAL (`ArgusWidget._mover_vinculado_ao_painel`), não o painel; o
  painel já segue a principal sozinho (`moveEvent`), então os dois andam
  juntos como um bloco só. Só em modo destacado a barra move a própria
  janela (independente por definição). Copiar código do ticket ao clicar no
  código. Destacar/Reanexar virou um único ícone de alfinete (📌 normal =
  Destacar, 📌 riscado = Reanexar - `_BotaoIcone.definir_riscado`, uma linha
  diagonal "\" desenhada na mão por cima do emoji, em vez de um segundo
  emoji - nenhum emoji de "despinar" rende de forma confiável em toda
  fonte/SO; a diagonal foi invertida (2026-08-16, pedido do usuário: "inverte
  o bloqueio no alfinete, ta se sobrepondo e mal da p ver") de "/" pra "\",
  cruzando menos o corpo do glifo).
- **Botões/campos no PADRÃO VISUAL DA GAIA (2026-08-16, pedido do usuário:
  "os botões eu quero eles no padrão da GAIA. A GAIA vai ser o padrão de
  todos os projetos" - diretriz vale pra qualquer projeto novo/futuro, não
  só o Argus):** todo o visual de botão/campo do Argus foi trocado pelo
  MOLDE visual da GAIA (`assistant/ui/qt_widgets.py`/`ui/qt_painel.py`) - copiado
  (não importado, Argus continua standalone/leve, ver docstring do módulo):
  - `_BotaoIcone` deixou de ser um `QLabel` com clique atribuído e virou um
    `QPushButton` NATIVO (mesmo molde de `criar_botao_pequeno`) - fundo/borda
    SEMPRE visíveis (não só no hover), e o Qt já garante clique correto em
    QUALQUER ponto do botão de graça (resolve de vez o relatado "parece que
    tem que clicar na posição exata do texto/ícone" - não dependia mais do
    pixel do glifo desde a versão anterior, mas com `QPushButton` nem
    precisa mais calcular hit-area na mão).
  - `_botao_estilizado` ganhou variante `preenchido=True` (fundo dourado
    sólido pra ação PRINCIPAL - Salvar/Analisar/Copiar/Entendi) igual
    `criar_botao`; os secundários (Cancelar/Fechar/Abrir) continuam no
    estilo "outline".
  - `SpinboxCapsula`/`_CampoValorSpinbox` (campo numérico "Cápsula", botões
    +/- redondos) substituem o `QSpinBox` nativo (setinhas pequenas demais).
  - `Switch` (toggle animado, trilho + bolinha) substitui o `QCheckBox`
    nativo pra configurações liga/desliga (pedido do usuário: "eu prefiro
    toggle do q checkbox").
  - Fundo dos dialogs virou `BG_COLOR` (era `SURFACE_COLOR`), igual
    `ModalArgus` e os outros modais da GAIA.
  - `_DialogoConfiguracoes` virou cards (`QFrame` + título de seção +
    descrição, ver `_titulo_secao`/`_descricao`) em vez de um `QFormLayout`
    cru - mesmo molde do modal `ModalArgus`
    (`assistant/ui/qt_modais/argus.py`, que já existe do lado da GAIA pras
    configurações de voz/notificação do Argus - este dialog aqui é as
    configurações da UI do widget em si, escopo diferente).
  - O código do ticket (clique pra copiar) usa `_RotuloClicavel` (override
    de CLASSE do `mousePressEvent`, nunca `label.mousePressEvent =
    lambda...` por instância) + padding reservado, já que não tem
    equivalente direto no catálogo da GAIA (texto rico colorido por
    prioridade, não um emoji fixo).
- **Causa raiz de "linhas/chips sobrepostos" achada investigando os bugs
  relatados (correção 2026-08-16):** em TODO lugar que reconstrói uma lista
  (barra de categorias, lista de tickets, campos do painel de detalhes), o
  padrão de sempre era `layout.takeAt(0)` + `widget.deleteLater()` - só que
  `deleteLater()` sozinho destrói o widget numa volta FUTURA do loop de
  eventos; até lá ele continua VISÍVEL na última posição (`takeAt`/
  `removeWidget` só param de gerenciar a geometria, não escondem nada),
  sobreposto ao conteúdo novo que acabou de ocupar aquele mesmo espaço.
  Corrigido chamando `widget.hide()` ANTES do `deleteLater()` nos três
  pontos (`_reconstruir_barra`, `_preencher_painel`,
  `_PainelDetalhesTicket.preparar_conteudo`) - esconde na hora, de forma
  síncrona; a memória continua sendo limpa depois.
- **Segunda causa raiz da MESMA família - "quando clico no desfixar ele zoa
  os botões" (correção 2026-08-16, print de tela real anexado pelo
  usuário):** a correção acima só escondia widgets adicionados DIRETO no
  layout - só que `preparar_conteudo` também tem SUB-layouts aninhados
  (`linha_arraste`/`linha_topo`/`linha_botoes`, via `addLayout`), e
  `item.widget()` devolve `None` pra um item que é um LAYOUT em vez de um
  widget - a limpeza nunca enxergava/escondia os widgets DENTRO desses
  sub-layouts (título, ícones, botões de ação), que ficavam órfãos e
  VISÍVEIS na posição antiga toda vez que `preparar_conteudo` rodava de novo
  na MESMA instância (abrir no anexado + destacar, por exemplo) - dava
  exatamente a impressão de "título/botões duplicados". Corrigido com
  `_limpar_layout(layout)`, uma limpeza RECURSIVA que desce em qualquer
  sub-layout encontrado (não só o nível 1).

Ver `testes/testar_painel_detalhes_anexado_destacado.py` pra validação do
fluxo completo (anexar, trocar de ticket, destacar, reanexar, limite,
cascata, destaque da lista, fechamento).

**Toggle + limpar novidade ao abrir (2026-08-21, pedido do usuário: "em vez
de só sair de novo quando clicar em abrir, tira quando clico no campo")** -
antes, `ArgusWidget._ticket_clicado` só saía marcando `visto` (limpando a
novidade) ao clicar no botão "Abrir" (o link do Jira, ver `_abrir_ticket`);
clicar de novo no MESMO ticket já aberto no painel anexado não fazia nada.
Agora:
- Abrir um ticket (clicar no campo da lista) já marca `visto` na hora, se
  ele estava `novo` - não precisa clicar "Abrir" pra isso (`_abrir_ticket`
  continua marcando visto também, sem problema - é idempotente). Muda só o
  objeto `Ticket` em memória + `_reconstruir_barra()`, sem `atualizar()`
  completo (que recarrega tudo do Jira) - não pesa a rede num clique comum.
- Clicar de novo no MESMO ticket já aberto no anexado agora FECHA o painel
  (toggle) - reaproveita `_fechar_anexado_se_visivel`, mesmo método já usado
  quando uma janela destacada volta ao foco. Ticket já destacado continua só
  trazendo a janela pra frente (ver "Controle de instâncias" acima).
- Consequência esperada (não é bug novo): se abrir um ticket zera as
  novidades da categoria, e o Argus está no modo "novidades" (ver "Modelo de
  interação da UI" abaixo), a lista se fecha sozinha - mesmo comportamento
  que já existia pra quando "Abrir" zerava a última novidade, só que agora
  também disparado pelo clique no campo.

**Campo INTEIRO clicável de verdade (2026-08-21, pedido do usuário: "a
seleção no campo tem de ser se o mouse estiver no espaço inteiro, não apenas
no texto, tem que permitir clicar na parte vazia também")** - `_LinhaTicket`
já tinha `mousePressEvent` no widget da linha inteira, mas os dois `QLabel`
internos (código+pontuação, resumo) ficam por CIMA dele e engolem o clique
antes que chegue no pai (mesma pegadinha real do Qt já documentada pro
scroll em `_RepassaRoda`) - na prática só os vãos vazios (margem, espaço
entre os dois labels) respondiam de forma confiável. Corrigido com
`Qt.WA_TransparentForMouseEvents` nos dois `QLabel` - o clique atravessa
direto pro `_LinhaTicket` em QUALQUER ponto da linha, texto ou vazio.

**Mesma pegadinha na CATEGORIA da barra (2026-08-23, pedido do usuário: "o
ticket só é selecionado se passar o mouse sobre o texto dele, tem de ser
sobre todo o botão")** - achado investigando esse relato: `_ChipCategoria`
(a cápsula "Aguardando Atendimento (5)" na barra) tem a MESMA estrutura de
`_LinhaTicket` - um widget com `mousePressEvent`/`enterEvent`/`leaveEvent`
próprios, mas com `QLabel`s internos (bolinha, nome, badge do contador) por
cima engolindo o evento antes de chegar no chip. Confirmado com
`chip.childAt(ponto)` (o mesmo hit-test que o Qt usa de verdade pra
clique/hover): sobre o texto/badge devolvia o `QLabel` filho, não o chip -
só a borda/vão vazio respondia de forma confiável. Corrigido com o mesmo
`Qt.WA_TransparentForMouseEvents` nos três `QLabel` internos (bolinha, nome,
badge). `_LinhaTicket` (linha do ticket na lista) já tinha sido corrigido
antes (ver acima) e foi reconfirmado com o mesmo teste de `childAt()` -
continua correto em qualquer ponto da linha.

## Resiliência a falha de rede (2026-08-23)

Reportado tentando abrir o Argus pela GAIA: `HTTPSConnectionPool... Connection
to nordwareservices.atlassian.net timed out` - uma falha de rede/timeout
transitória (comum, não é um bug do Jira nem de credencial) ao buscar os
tickets derrubava a criação do `ArgusWidget` INTEIRO, porque `atualizar()`
(quem chama `self._provider.listar_categorias()`) roda dentro do próprio
`__init__`. O widget nem chegava a existir - `ui/qt_painel.py::_abrir_argus_widget`
(GAIA) capturava a exceção e só mostrava "Não consegui abrir o Argus: ...".

`ArgusWidget.atualizar()` agora envolve a busca num `try/except Exception`
amplo (não um tipo específico de exceção de rede - o `core/` não sabe/não
deveria saber que o provider por baixo usa `requests`, só a interface
`NotificacaoProvider`) - uma falha só loga no console e mantém `self._categorias`
como estava (vazia, na primeira abertura; a última lista boa, num poll
seguinte). Como `atualizar()` também é o método chamado pelo `QTimer` de
polling (a cada `ARGUS_INTERVALO_POLLING_SEGUNDOS`), essa mesma proteção
cobre os dois casos: falha na abertura E falha durante o uso normal (sem
isso, um Wi-Fi instável quebraria o polling silenciosamente a cada ciclo
ruim). Tenta de novo sozinho no próximo ciclo, sem exigir reabrir o Argus.

**Segunda causa raiz da MESMA família, achada em uso real (2026-08-23):** o
fix acima protege a ABERTURA do widget, mas o usuário relatou de novo
("clicando no icone do argus e ele nao esta expandindo p mostrar as
opcoes") - o widget abria (sem crash), mas a barra de categorias ficava
sempre vazia, mesmo com a rede voltando a funcionar às vezes. Causa raiz
real, achada lendo `logs/AAAA-MM-DD.log` (onde o `print()` do fix anterior
realmente aparece, já que `run.py` roda sem console): `JiraProvider.
buscar_dados_brutos()` processa as 4 categorias e todos os tickets de cada
uma num loop só, SEM isolamento nenhum - um timeout processando UM ticket
(SLA, changelog de status, issue vinculado de 2 saltos) ou buscando a JQL
de UMA categoria lançava uma exceção que subia até o topo da função INTEIRA,
descartando os dados de TODAS as categorias, mesmo as que já tinham sido
buscadas com sucesso um instante antes no mesmo ciclo. Como isso repetia a
cada poll, a barra nunca chegava a mostrar nada.

Corrigido isolando cada categoria (a busca JQL) e cada ticket (o
processamento de SLA/changelog/vínculo/urgência) no próprio
`try/except requests.RequestException` - uma falha vira só um log
(`buscar_dados_brutos`) e aquela categoria/ticket fica de fora SÓ NESTE
ciclo, sem descartar o que já tinha dado certo. Validado com um `JiraProvider`
onde uma categoria inteira falha na busca E um ticket específico falha só no
SLA - confirmado que o ticket bom da mesma categoria e as outras categorias
continuam aparecendo normalmente.

**Busca em thread própria (2026-08-23, reportado pelo usuário: "pq demora p
abrir o argus pela gaia"):** `self._provider.listar_categorias()` faz várias
chamadas de rede sequenciais (JQL ×4 + SLA/changelog/issue vinculado por
ticket) e essa função rodava direto na thread da UI - como `atualizar()`
roda dentro do próprio `__init__`, abrir o Argus pela GAIA travava a JANELA
PRINCIPAL inteira (Painel, bandeja, tudo) até a busca terminar, o que podia
levar bastante tempo com a rede instável observada nesta mesma sessão
(vários timeouts de 15s por chamada). `atualizar()` agora lança a busca numa
`_TarefaSegundoPlano` (mesmo `QThread` já usado pelo botão "Analisar") - o
widget abre e a janela principal continua responsiva na hora; os dados
chegam e populam a barra assim que a busca terminar
(`_ao_atualizar_concluido`/`_ao_atualizar_falhou`, sempre entregues de volta
na thread da UI via Signal - nunca mexendo em widget Qt de dentro da thread
de fundo). Uma chamada de `atualizar()` enquanto a busca anterior ainda
está rodando simplesmente não empilha outra (`self._tarefa_atualizacao.
isRunning()`).

**Efeito colateral nos testes offscreen:** como a primeira carga não é mais
síncrona, os 3 scripts em `testes/` que inspecionam `widget._categorias`
logo após `widget.show()` precisaram de `widget._tarefa_atualizacao.wait()`
+ dois `app.processEvents()` (o primeiro entrega o Signal de conclusão, que
só ENTÃO agenda o `singleShot(0)` de `_atualizar_painel_se_aberto` - o
segundo esvazia esse timer) antes de continuar. Sem a segunda rodada, esse
timer ficava pendente e disparava mais tarde, no meio de alguma interação
não relacionada do teste - achado real rodando a suíte (regressão no teste
de encolhimento de janela, "altura com categoria grande" saindo errada).

**Retentativa no HTTP de mais baixo nível (2026-08-23):** os fixes acima
protegem contra uma falha de rede DEPOIS que a requisição já falhou, mas
nenhum deles evita a falha em si. Confirmado repetidas vezes nesta mesma
investigação (várias sessões, vários endpoints diferentes) que
`nordwareservices.atlassian.net` engasga de forma transitória e
praticamente sempre responde numa segunda tentativa - inclusive o PRÓPRIO
`GET /rest/api/3/myself` chamado no `__init__` do `JiraProvider` (pra
descobrir a conta do usuário), que ficava de FORA de todos os fixes
anteriores (eles protegem `atualizar()`/`buscar_dados_brutos()`, não a
construção do provider em si) - uma falha ali derrubava a abertura do Argus
antes mesmo do `ArgusWidget` existir. `JiraProvider._obter` (o único ponto
por onde passa TODA chamada HTTP da classe) agora tenta até 3 vezes com 2s
de intervalo, só em cima de `ConnectionError`/`Timeout` (erro de
conexão/timeout de verdade) - um erro HTTP de status (401 credencial
errada, 404 issue não existe) sobe na hora, sem esperar, porque tentar de
novo não muda o resultado.

## Causa raiz real do clique/hover fora do texto (2026-08-23)

Os fixes anteriores (`Qt.WA_TransparentForMouseEvents` em `_LinhaTicket` e
`_ChipCategoria`, ver seções acima) resolveram o roteamento de evento
DENTRO do Qt (qual widget recebe o clique), mas o usuário continuou
relatando "só seleciona em cima do texto" mesmo depois de confirmado que o
código estava instalado e a Galateia reiniciada. Investigação com dois
diagnósticos visuais manuais (`testes/diagnostico_hover_linha_ticket.py` e
`testes/diagnostico_hover_argus_real.py`, este último sobe o `ArgusWidget`
DE VERDADE com as mesmas flags de janela) isolou a variável real: o
`_LinhaTicket` sozinho, numa janela NORMAL/opaca, respondia certinho em
qualquer ponto da linha - só falhava dentro da janela FLUTUANTE real do
Argus (sem borda, sempre no topo, `WA_TranslucentBackground` + Acrylic).

**Causa raiz:** `background-color: transparent` é alpha ZERO de verdade.
Numa janela translúcida do Windows, uma área com alpha zero é tratada como
CLIQUE-ATRAVÉS pro que estiver atrás da janela no desktop - o evento nem
chega a ser entregue à aplicação, muito menos ao Qt. Só os GLIFOS DE TEXTO
(pintados pelos `QLabel` por cima, com cor opaca) tinham alpha > 0 e por
isso respondiam; o resto da linha/chip (fundo "transparent" em repouso)
ficava "morto" pro mouse - um problema de NÍVEL DE JANELA (Windows decidindo
se entrega o evento), completamente diferente do problema de roteamento
DENTRO do Qt que os fixes anteriores resolveram (por isso pareciam
"corrigidos" nos testes automatizados/offscreen, que não simulam esse
comportamento do compositor de verdade).

**Correção:** `_LinhaTicket._atualizar_estilo` e `_ChipCategoria.
definir_aberta` trocaram `"transparent"` por um alpha quase-zero no FUNDO
do estado de repouso - "pintado" o suficiente pro Windows não tratar aquela
área como clique-através, mas imperceptível a olho nu. A BORDA
(`border: 1px solid ...`) ficou de fora do fix de propósito - é um traço de
1px, não uma área onde alguém tenta clicar, e um traço fino com alpha baixo
fica mais perceptível (antialiasing "arredonda pra cima" a opacidade
percebida) do que a mesma cor numa área grande de preenchimento - continua
`"transparent"` de verdade.

**Duas rodadas até acertar o valor (2026-08-23):** primeira tentativa foi
`rgba(0, 0, 0, 1)`, pensando em "1 de 255" (quase nada). Resultado real
(print de tela do usuário): um retângulo PRETO SÓLIDO atrás de cada
ticket/cápsula, o oposto do pretendido - `rgba()` no QSS/CSS usa alpha como
FRAÇÃO 0.0-1.0, não um inteiro 0-255, então `1` ali significa opacidade
TOTAL. Corrigido pra `rgba(0, 0, 0, 0.004)` (≈1/255, o valor que a
intenção original queria dizer). Validado ao vivo pelo usuário com o
diagnóstico visual (`diagnostico_hover_argus_real.py`) rodando a janela
real do Argus - clique/hover funcionando fora do texto, sem nenhum fundo
escuro visível.

## Menu de Configurações (2026-08-16)

As duas opções que antes só davam pra mudar editando `.env`/constante no
código (limite de janelas destacadas, chacoalhada de atenção - ver seção
acima) ganharam um menu de verdade: `_DialogoConfiguracoes`
(`argus/core/widget.py`), aberto via `ArgusWidget.abrir_configuracoes()` -
no uso standalone, ligado ao item "Configurações..." da bandeja do sistema
(`app.py`); rodando embutido, quem instanciar o `ArgusWidget` pode ligar isso
na própria UI do mesmo jeito (método público).

- Persistido via `Persistencia.obter/salvar_configuracoes(dict)` - método NÃO
  abstrato (pra não quebrar implementações de `Persistencia` já existentes
  fora deste repo, ex. o adaptador da GAIA) e GENÉRICO (um dict, não um par
  por opção) pra não precisar estender a interface de novo a cada
  configuração nova que o menu ganhar.
- Config salva tem prioridade sobre o argumento do construtor (que no uso
  standalone vem do `.env`) - se o usuário já mudou algo pelo menu, isso
  prevalece entre reinícios.
- Aplica em TEMPO REAL, sem reiniciar o Argus: `_PainelDetalhesTicket` recebe
  um CALLABLE (`obter_chacoalhada_ativa`, não um bool capturado na criação) -
  painéis já abertos (anexado ou destacados) refletem a mudança na hora,
  porque todos compartilham a mesma leitura de `ArgusWidget._chacoalhada_ativa`.

Ver `testes/testar_configuracoes.py`.

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
