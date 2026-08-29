# Changelog

Histórico de alto nível do que muda no Argus, por versão. Detalhe técnico completo
de cada decisão está em `ARQUITETURA.md`. Este arquivo é o resumo pra quem só
quer saber "o que mudou", sem reabrir o PR mesclado no GitHub.

Versionamento: [Semantic Versioning](VERSIONAMENTO_CHANGELOG.md).

## [Unreleased]

## [0.7.0] - 2026-08-28: Tooltip de pontuação de foco + cor do título por SLA

### Novidades
- Passar o mouse somente sobre o número `[pontuação]` de um ticket agora mostra como a pontuação de foco foi calculada: base da prioridade do Jira, bônus de urgência textual, bônus de SLA, eventual piso por urgência e teto de 100. O restante da linha continua sem tooltip.
- **Título do ticket na lista muda de cor por SLA** - vermelho se estourado, laranja faltando menos de 1h, amarelo faltando menos de 2h. Ganhou também um sufixo compacto com o tempo restante em horas inteiras, `(2h)` restando ou `(-4h)` estourado. Ver `ARQUITETURA.md`.

### Correções
- **Tooltips com fundo preto padrão do Qt, fora da paleta do Argus** - nenhum `QToolTip` tinha estilo próprio (pontuação, "Arrastar", botões de ícone, código do ticket). Corrigido com uma regra `QToolTip` global em `aplicar_estilo_global` (`core/tema.py`), cobrindo todos de uma vez.

## [0.6.6] - 2026-08-24: Lembrete de voz da GAIA não via ticket já visto no widget

### Correções
- `PersistenciaArquivo` carregava o arquivo (`~/.argus/config.json`) 1x na criação e guardava numa cópia em memória (`self._dado`) que nunca era recarregada - a GAIA mantém sua própria instância de longa duração (1x por processo) separada da instância que o widget usa (criada só quando o widget abre), então quando o usuário via um ticket no widget, a instância da GAIA continuava com o snapshot antigo pra sempre e o lembrete de voz seguia dizendo "tem ticket pendente" mesmo já visto. Corrigido lendo do disco a cada chamada (arquivo pequeno, custo desprezível) em vez de cachear em memória.

## [0.6.5] - 2026-08-23: Preto sólido indesejado no fix do clique-através

### Correções
- O fix do clique-através (`rgba(0, 0, 0, 1)` no fundo em repouso) virou um retângulo PRETO SÓLIDO atrás de cada ticket/cápsula, em vez de imperceptível - `rgba()` no QSS/CSS usa alpha como fração 0.0-1.0, não um inteiro 0-255, então `1` significava opacidade total, não "1 de 255". Corrigido para `rgba(0, 0, 0, 0.004)` (≈1/255), o valor que a intenção original queria dizer.

## [0.6.4] - 2026-08-23: Borda escura indesejada no fix do clique-através

### Correções
- O fix do clique-através (alpha 1 em vez de "transparent") tinha sido aplicado também na BORDA de 1px da linha/cápsula, que ficou visível como um traço escuro em volta de cada ticket - antialiasing de um traço fino "arredonda pra cima" a opacidade percebida, diferente de uma área grande de preenchimento. Borda voltou a ser transparente de verdade; só o preenchimento (que é o que precisa não ser clique-através) ficou com alpha 1.

## [0.6.3] - 2026-08-23: Causa raiz real do clique/hover fora do texto

### Correções
- Ticket/categoria continuavam só respondendo a clique/hover em cima do texto mesmo depois dos fixes anteriores - causa raiz real (achada com um diagnóstico visual rodando a janela de verdade do Argus): fundo `transparent` é alpha zero de verdade, e numa janela translúcida (`WA_TranslucentBackground` + Acrylic, como a do Argus) o Windows trata isso como clique-através pro que estiver atrás na área de trabalho - só os glifos de texto (opacos) respondiam. Corrigido usando `rgba(0, 0, 0, 1)` (imperceptível, mas tecnicamente pintado) em vez de `transparent` no repouso da linha do ticket e da cápsula de categoria.

## [0.6.2] - 2026-08-23: Retentativa em toda chamada HTTP do Jira

### Correções
- `GET /rest/api/3/myself` (chamado no `__init__` do `JiraProvider`, pra descobrir a conta do usuário) podia falhar por timeout transitório e derrubar a abertura do Argus antes mesmo do widget existir - ficava de fora dos fixes de resiliência anteriores, que só protegem `atualizar()`. Corrigido no ponto mais baixo: `JiraProvider._obter` (por onde passa toda chamada HTTP da classe) agora tenta até 3 vezes com 2s de intervalo em erro de conexão/timeout - erro de status HTTP (401, 404) continua subindo na hora, sem retentar.

## [0.6.1] - 2026-08-23: Categoria da barra clicável em qualquer ponto

### Correções
- A cápsula de categoria na barra ("Aguardando Atendimento (5)") só registrava clique/hover de forma confiável nos vãos vazios (borda) - o texto e o badge do contador engoliam o evento antes de chegar no chip, mesma pegadinha já corrigida na linha do ticket. Corrigido deixando os `QLabel` internos (bolinha, nome, badge) transparentes a mouse.

## [0.6.0] - 2026-08-23: Painel de detalhes anexado/destacado, robustez de rede e correções de clique

### Novidades
- Painel de detalhes reescrito como extensão visual do Argus: fica **anexado** (segue a janela principal; clicar em outro ticket fecha o anterior e abre um novo, na hora, sem animação) e pode ser **destacado** em janela independente arrastável via uma pequena barra centralizada no cabeçalho.
- Controle de instância: cada ticket abre no máximo 1 painel (nunca duas janelas pro mesmo ticket) - clicar num ticket já destacado traz a janela pra frente com um pulso de atenção na borda.
- Posicionamento consciente de múltiplos monitores (área útil, recalcula o lado ao trocar de monitor) e limite configurável de janelas destacadas.
- Menu "Configurações..." na bandeja do sistema (`_DialogoConfiguracoes`): limite de janelas destacadas e chacoalhada de atenção agora são ajustáveis em tempo real e persistidos, sem precisar editar `.env`/código.
- Ações rápidas do painel de detalhes viraram ícones compactos em vez de botões de texto: 🔗 Copiar link colado no código do ticket (à esquerda do cabeçalho), 📌 alfinete pro par Destacar/Reanexar (riscado quando já destacado) ao lado de ⟳ Atualizar e do ✕ Fechar (à direita), "Abrir no Jira" resumido pra "Abrir". Copiar código do ticket ao clicar no código.
- Botões e campos do Argus passaram a seguir o PADRÃO VISUAL DA GAIA (agora o padrão de todos os projetos): ícones do cabeçalho viraram `QPushButton` nativo (era `QLabel`), variante de botão "preenchido" (dourado) pras ações principais, campo numérico "Cápsula" (era `QSpinBox` nativo) e toggle animado `Switch` (era `QCheckBox`) no menu de Configurações, que também ganhou layout em cards.
- Mudança de status feita pelo próprio usuário deixou de contar como novidade - o ticket continua indo pra coluna/categoria certa, só não dispara mais aviso de voz nem o badge "NOVO" (checa o autor da última transição via changelog do Jira, só quando o status realmente mudou).
- Clicar de novo no ticket já aberto no painel anexado agora FECHA o painel (toggle) - antes só saía marcando visto ao clicar "Abrir" (o link do Jira) ou ao trocar de ticket. Abrir o ticket no painel (clicar no campo da lista) já limpa a novidade dele na hora, sem precisar clicar "Abrir".

### Correções
- Destacar vários tickets em seguida sem arrastar nenhum antes fazia as janelas independentes nascerem exatamente sobrepostas (empilhadas, indistinguíveis) - corrigido com um deslocamento em cascata a cada nova janela destacada.
- Selecionar um ticket e depois outro não trocava o painel de forma confiável e podia deixar tickets sobrepostos na lista - a primeira versão (uma instância reaproveitada com crossfade animado) se mostrou frágil em uso real. Simplificado: cada ticket clicado fecha o painel anterior e abre um novo do zero, sem animação nem estado intermediário.
- Causa raiz mais ampla encontrada investigando o item acima: ao reconstruir a barra de categorias/lista de tickets/painel de detalhes, os widgets antigos removidos do layout só eram marcados com `deleteLater()` - continuavam VISÍVEIS na posição antiga (sobrepostos ao conteúdo novo) até uma volta futura do loop de eventos. Corrigido escondendo (`hide()`) o widget antigo na hora, em todos os pontos que recriam listas.
- Botões pareciam exigir clicar exatamente em cima do texto/ícone - resolvido de vez trocando o `QLabel` customizado por um `QPushButton` nativo (padrão da GAIA), que já garante clique em qualquer ponto do botão.
- Arrastar a janela destacada não funcionava de forma confiável (área de arraste invisível ocupando todo o cabeçalho) - trocado por uma pequena barra de arraste sempre visível (em qualquer estado, anexado ou destacado), centralizada e posicionada ACIMA da linha de botões.
- Removido o botão de redimensionar da janela destacada (relatado causando duplicação de botões) - painel destacado agora tem tamanho fixo, só arrastável.
- Corrigido o mesmo tipo de duplicação de botões relatado (com print de tela) ao clicar em "Reanexar": `preparar_conteudo` tem sub-layouts aninhados (título/ícones/ações), e a limpeza anterior só alcançava widgets diretos - título e botões antigos ficavam órfãos e visíveis por cima dos novos toda vez que o conteúdo era reconstruído na mesma janela. Limpeza agora é recursiva (`_limpar_layout`).
- Arrastar a barra do painel ANEXADO agora move a janela principal junto (antes só movia o painel, "desgrudando" visualmente da barra de status enquanto ainda vinculado) - o painel continua seguindo a principal sozinho, então os dois andam como um bloco só.
- Invertida a diagonal do alfinete "riscado" (Reanexar) - cruzava demais o corpo do emoji e ficava pouco legível.
- Destacar um ticket, abrir outro (no anexado) e depois voltar no destacado deixava os dois "selecionados" ao mesmo tempo (painel anexado continuava aberto atrás da janela destacada trazida pra frente) - corrigido fechando o anexado sempre que uma janela destacada volta ao foco.
- A linha de um ticket na lista só registrava clique nos vãos vazios (margem/espaço entre o código e o resumo) - o texto em si engolia o clique (mesma pegadinha do Qt já documentada pro scroll, ver `_RepassaRoda`), então na prática só uma fração pequena da linha respondia de forma confiável. Corrigido deixando os `QLabel` internos transparentes a mouse - o clique atravessa pra linha em QUALQUER ponto, texto ou vazio.
- Uma falha de rede/timeout transitória ao consultar o Jira (relatado ao tentar abrir o Argus pela GAIA: "Connection to nordwareservices.atlassian.net timed out") derrubava a criação do widget inteiro, já que `atualizar()` roda dentro do próprio `__init__` - o Argus simplesmente não abria. Corrigido: uma falha em `atualizar()` agora só é logada e mantém os dados que já existiam (vazio, na primeira abertura); o próximo ciclo do polling tenta de novo sozinho, sem precisar reabrir.
- Mesmo depois do fix acima, o widget abria mas a barra de categorias ficava sempre vazia ("clicando no icone do argus e ele nao esta expandindo p mostrar as opcoes") - uma falha de rede processando UM ticket (SLA, changelog, issue vinculado) ou buscando UMA categoria descartava os dados de TODAS as categorias daquele ciclo, mesmo as que já tinham sido buscadas com sucesso. Corrigido isolando cada categoria e cada ticket no próprio try/except - uma falha agora só descarta aquela categoria/ticket específica, não o ciclo inteiro.
- Abrir o Argus pela GAIA travava a janela principal inteira até a busca no Jira terminar (várias chamadas de rede sequenciais por ticket - podia levar bastante tempo com a rede instável). A busca agora roda numa thread própria - o widget abre na hora e a janela principal continua responsiva enquanto os dados carregam.

## [0.5.1] - 2026-08-15: Documentação em dia + origem do nome do repo

### Alterado
- `README.md`/`ARQUITETURA.md`/`CLAUDE.md` atualizados pra refletir o estado real do projeto (motor, pontuação de foco, painel de detalhes, ícone oficial). Documentada a origem do nome "Argus" (mito de Argos Panoptes, o gigante de cem olhos) e o rename do repo.

## [0.5.0] - 2026-08-15: Painel de detalhes do ticket + análise via LLM

### Novidades
- Clicar num ticket abre um painel de detalhes (Time to resolution, Plataforma, Empresa, Relator, Responsável, Tipo de solicitação).
- Botão "Analisar" (gancho de LLM opcional, injetado por quem consome o Argus): busca descrição + todos os comentários sob demanda e gera um rascunho de resposta ao cliente, revisável antes de copiar - nunca posta no Jira sozinho.

## [0.4.0] - 2026-08-15: Cores de prioridade real do Jira no ticket

### Novidades
- Código do ticket colorido pela prioridade real (Highest/High/Medium/Low/Lowest), com legenda no painel.

### Correções
- Nome da prioridade aparecia repetido no texto do ticket (já dava pra ver pela cor) - removido, só o código fica colorido.

## [0.3.3] - 2026-08-15: Escalonamento de SLA e correção de urgência

### Correções
- Bônus de SLA estourado era fixo (+25), não importava se o estouro tinha 1 minuto ou 20 horas - passou a escalar pela hora real de atraso.
- Um piso fixo (85) testado pra qualquer SLA estourado resolveu o caso original mas criava outro: algo mais crítico (ex.: prioridade High recém-aberta) ficava atrás de uma Lowest com SLA estourado há pouco. Piso fixo removido; ganhou um piso equivalente (75) pra urgência CONFIRMADA no texto, sinal mais confiável que o relógio do SLA sozinho.
- Detecção de urgência no texto dava falso positivo em frase negada ("não é urgente" continha a substring "urgente") - corrigido removendo o trecho negado antes de procurar as palavras-chave.

## [0.3.2] - 2026-08-15: Separa busca de classificação no JiraProvider

### Correções
- `listar_categorias()` fazia a busca completa na API do Jira 2 vezes por ciclo quando consumido por dois checadores com persistências diferentes (voz + lembrete de não visualizado) - separado em `buscar_dados_brutos()`/`classificar()`, busca 1 vez só e classifica em memória quantas vezes precisar.

## [0.3.1] - 2026-08-15: Ícone oficial

### Novidades
- Ícone oficial (pavão de cristal, remete ao mito de Argos Panoptes) substituindo o círculo dourado provisório na bandeja do sistema, no ícone da janela e no placeholder da personagem.

## [0.3.0] - 2026-08-15: Pontuação de foco, mascaramento e análise de imagem

### Novidades
- Pontuação de foco (1-100): prioridade real + urgência no texto (heurística PT-BR, sem LLM) + SLA real (Time to resolution) - só ordena/exibe, nunca escreve no Jira.
- Mascaramento de dado sensível (senha/token/CPF/CNPJ/cartão) antes de qualquer análise de texto.
- Análise de imagem opcional (gancho de LLM injetado - o Argus em si não depende de nenhuma LLM) quando o ticket tem print anexado, mesmo com descrição/comentário já preenchidos.

## [0.2.0] - 2026-08-15: Redesenho visual

### Novidades
- Redesenho visual completo do widget + lançadores sem console (`.bat`/`.vbs`).
- Efeitos DWM (cantos redondos, Acrylic, Mica) via `win32_dwm.py` - Mica testado visualmente e mantido desligado por padrão (material claro não combinou com a paleta escura do widget).

### Correções
- Badge esticando, scroll parcial e anel cortado - corrigidos, e um evento (mudança de status/atribuição/comentário/prioridade) passou a ser classificado antes de virar novidade.

## [0.1.0] - 2026-08-15: Estrutura inicial do Argus

### Novidades
- Motor completo (fase 1): barra flutuante por categoria (Em Revisão/Aguardando Atendimento/Aguardando Cliente/Aguardando Desenvolvimento), modos novidade/total, `JiraProvider` com os 4 status + vínculo de 2 saltos pra "Aguardando Desenvolvimento".

### Correções
- Busca JQL usava o NOME do status em vez do ID - corrigido.
