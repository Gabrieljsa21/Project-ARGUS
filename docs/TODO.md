# TODO - Argus

Convenção: cada item tem **Prioridade** (Alta/Média/Baixa), **Complexidade**
(Alta/Média/Baixa) e **Status**. Remover o item daqui quando implementado
(nunca só marcar como feito) - ver `ARQUITETURA.md` pra decisão técnica
correspondente.

## Copiloto de classificação via IA (proposta, ainda não implementada)

Origem: apresentação `Techtalk-Completa-Apresentador.html`
(`E:\Downloads\Tech Talk`), evolução do que já foi portado do
`triagem-inteligente-prototipo` pra `pontuacao.py`/`seguranca.py` (heurística
por palavra-chave). Esta proposta vai além: um classificador real via LLM,
com sugestão revisável pela pessoa, nunca aplicando nada sozinho no Jira.

Roadmap em 4 etapas pequenas, cada uma produzindo evidência antes de
aumentar a complexidade - não pular etapa.

- [ ] **Etapa 1 - Exemplos fictícios**
  Prioridade: Média | Complexidade: Baixa | Status: 💡 Ideia
  Dataset de chamados fictícios (sem dado real de cliente) pra testar o
  classificador com segurança, mesmo espírito do `ChamadosFicticios.cs` do
  protótipo original.

- [ ] **Etapa 2 - Classificador separado (protótipo isolado)**
  Prioridade: Média | Complexidade: Alta | Status: 💡 Ideia
  IA com saída estruturada (Structured Outputs) devolvendo `tipo`, `sistema`,
  `urgente` e `motivo` em JSON fixo, campos e opções definidos pela
  aplicação (não texto livre). Roda fora da tela principal do Argus, sem
  integração com o widget ainda. Depende de decisão de provedor de IA
  (chave própria, orçamento).

- [ ] **Etapa 3 - Medir resultados (Eval com histórico real do Jira)**
  Prioridade: Média | Complexidade: Alta | Status: 💡 Ideia
  Comparar chamados com tipo alterado durante o atendimento (correção
  humana) contra chamados estáveis, pra medir se a IA teria classificado
  certo já na abertura. Confiança vem do teste contra casos reais, não da
  nota de confiança que a própria IA reporta. Sem agir nos chamados nesta
  etapa.

- [ ] **Etapa 4 - Copiloto integrado no Argus**
  Prioridade: Baixa | Complexidade: Alta | Status: 💡 Ideia
  Sugestão exibida na UI com **Confirmar / Corrigir / Ignorar** - só uma
  ação confirmada pela pessoa muda o chamado, a IA nunca aplica nada
  sozinha. Sempre reversível; se a IA falhar ou demorar, o Argus continua
  funcionando como hoje.

### Segurança adicional a cobrir antes da Etapa 2

- [ ] Defesa contra prompt injection: texto do chamado tratado como dado,
  nunca como instrução (frases tipo "ignore as instruções" não podem
  alterar o comportamento do classificador).
- [ ] Resposta da IA restrita a opções pré-definidas pela aplicação (não
  aceitar categoria/sistema fora do catálogo conhecido).
- [ ] Fluxo específico pra prints: leitura em ambiente controlado → texto
  extraído → mascaramento (`seguranca.py`) → classificação. Sem leitor
  interno, a imagem original teria que ir pro serviço de IA sem mascarar
  antes, o que não é aceitável.
