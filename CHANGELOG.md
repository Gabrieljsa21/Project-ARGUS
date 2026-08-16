# Changelog

Histórico de alto nível do que muda no Argus, por PR. Detalhe técnico completo
de cada decisão está em `ARQUITETURA.md`. Este arquivo é o resumo pra quem só
quer saber "o que mudou", sem reabrir o PR mesclado no GitHub.

## [Unreleased]

### Novidades
- Motor completo: barra flutuante por categoria (Em Revisão/Aguardando Atendimento/Aguardando Cliente/Aguardando Desenvolvimento), modos novidade/total, `JiraProvider` com os 4 status + vínculo de 2 saltos pra "Aguardando Desenvolvimento".
- Pontuação de foco (1-100): prioridade real + urgência no texto (heurístico PT-BR, sem LLM) + SLA real (Time to resolution) - só ordena/exibe, nunca escreve no Jira. Mascaramento de dado sensível (senha/token/CPF/CNPJ/cartão) antes de qualquer análise de texto.
- Análise de imagem opcional (Groq, gancho injetado - Argus em si não depende de LLM nenhuma) quando o ticket só tem print anexado.
- Cores de prioridade (Highest/High/Medium/Low/Lowest) no código do ticket + legenda no painel.
- Painel de detalhes por ticket (Time to resolution, Plataforma, Empresa, Relator, Responsável, Tipo de solicitação) com botão "Abrir ticket".
- Botão "Analisar" opcional (gancho de LLM injetado): busca descrição + todos os comentários sob demanda e gera rascunho de resposta ao cliente, revisável antes de copiar - nunca posta no Jira sozinho.
- Ícone oficial (pavão de cristal) substituindo o círculo dourado provisório - bandeja do sistema, ícone da janela e placeholder da personagem.
- Integração com a GAIA: widget visual na mesma `QApplication` do Painel + monitoramento de voz (só o `JiraProvider`, sem o widget) + gancho de análise via Groq.

### Correções
- Bônus de SLA estourado era fixo (+25, não importava quanto tempo passou do prazo) - agora escala por hora real de atraso; piso fixo testado e removido (empurrava até um SLA recém-estourado numa prioridade Lowest pra frente de um High genuinamente mais crítico) - piso equivalente foi pra urgência CONFIRMADA no texto, sinal mais confiável.
- Detecção de urgência no texto dava falso positivo em frase negada ("não é urgente" continha a substring "urgente").
- `listar_categorias()` fazia a busca completa na API do Jira 2x por ciclo quando consumido por dois checadores com persistências diferentes (fala por voz + lembrete de não-visualizado na GAIA) - separado em `buscar_dados_brutos()`/`classificar()`, busca 1x e classifica em memória quantas vezes precisar.
