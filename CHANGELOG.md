# Changelog

Histórico de alto nível do que muda no Argus, por versão. Detalhe técnico completo
de cada decisão está em `ARQUITETURA.md`. Este arquivo é o resumo pra quem só
quer saber "o que mudou", sem reabrir o PR mesclado no GitHub.

Versionamento: [Semantic Versioning](VERSIONAMENTO_CHANGELOG.md).

## [Unreleased]

### Novidades
- Painel de detalhes reescrito como extensão visual do Argus, não mais uma janela sempre recriada do zero: fica **anexado** (segue a janela principal, reaproveitado com crossfade entre tickets, animação de entrada, indicador de continuidade visual, destaque na lista) e pode ser **destacado** em janela independente (arrastável/redimensionável, posição/tamanho memorizados) via ação "Destacar"/"Reanexar".
- Controle de instância: cada ticket abre no máximo 1 painel (nunca duas janelas pro mesmo ticket) - clicar num ticket já destacado traz a janela pra frente com um pulso de atenção na borda.
- Posicionamento consciente de múltiplos monitores (área útil, DPI, recalcula o lado ao trocar de monitor) e limite configurável de janelas destacadas (`ARGUS_LIMITE_JANELAS_DESTACADAS`).
- Novas ações rápidas no painel: Copiar link e Copiar código do ticket (clique no código).

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
