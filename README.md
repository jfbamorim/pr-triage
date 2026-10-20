# PR Triage

Triagem de requisições de compra (Purchase Requisitions) para Purchasing / P2P. O utilizador escreve o pedido em texto livre, e a aplicação extrai os dados, valida, consulta a política de compras e devolve um estado com as cláusulas que o justificam.

**Princípio:** o LLM lê, extrai e explica. O Python decide. O modelo nunca aprova nada.

Projeto final do curso *Generative AI: Fundamentos e Aplicação* (EDIT).

## Como correr

```
uv sync
cp .env.example .env        # preencher OPENAI_API_KEY
uv run python scripts/run.py
```

O `run.py` constrói o índice da política na primeira execução e abre a interface em Streamlit. Para testes: `uv run pytest`. Para a avaliação: `uv run python eval/run_eval.py --split dev`.

## O problema

Quem faz compras recebe pedidos incompletos, mal escritos ou fora da política. A aplicação responde a três perguntas:

- O pedido está completo e é legítimo? Se faltam dados, pergunta; se é uma tentativa de manipulação, rejeita.
- Em que escalão de valor cai? Menos de 1 000 €, de 1 000 a 5 000 €, ou mais de 5 000 € (ação humana).
- Que cláusulas da política se aplicam, e o que dizem?

## O fluxo

![Fluxo](docs/fluxo.png)
![Resultado de um pedido](docs/captura-resultado.png)
![Pergunta de seguimento](docs/captura-pergunta.png)


| # | Passo | Quem faz |
|---|-------|----------|
| 1 | Verificar o texto (prompt injection) | LLM |
| 2 | Extrair os dados e juntar com o pedido anterior | LLM |
| 3 | Validar campos em falta ou inválidos | Python |
| 4 | Determinar o escalão de valor | Python |
| 5 | Consultar a política (RAG) | Embeddings + Chroma + Python |
| 6 | Decidir o estado e a escalação | Python |
| 7 | Resumo com citações | LLM, validado em Python |

Quando falham dados, o LLM escreve a pergunta de seguimento e o Python confirma que ela menciona cada campo em falta; se não, usa uma pergunta de recurso. Em qualquer falha (resumo inválido, política sem cláusulas relevantes, erro na consulta) o sistema falha para o lado seguro: passa para ação manual, nunca aprova.

## O que aprendi nas aulas e onde está no projeto

| Sessão | Tema | O que fiz | Onde |
|---|---|---|---|
| 1 | LLMs e APIs | Responses API com `gpt-4.1-mini`; chave e modelo no `.env`; temperature 0 nas decisões; tokens, latência e custo por chamada | `src/pr_triage/llm/`, `.env.example` |
| 2 | Prompting e structured outputs | Prompts com papel, tarefa, restrições e formato; saídas validadas com Pydantic; deteção de prompt injection; prompts com versão (`screening-v3`, `extraction-v5`, `summary-v4`, `followup-v1`) | `llm/`, `domain/schemas.py` |
| 3 | Embeddings e pesquisa semântica | `text-embedding-3-small`, Chroma, cosine similarity, `MIN_SCORE` calibrado com casos (0,52) para dizer "não há evidência" | `src/pr_triage/rag/` |
| 4 | RAG | Um chunk por cláusula, com id estável; contexto selecionado por escalão, categoria e urgência; citações obrigatórias, com ids validados | `rag/`, `domain/citations.py` |
| 5 | Medir, comparar e decidir | 50 casos etiquetados, divididos em `dev` e `holdout`; source recall; comparação de versões de prompt nos mesmos casos; tokens e latência por passo | `data/eval/cases.jsonl`, `eval/run_eval.py` |
| 6 | Conversational RAG e tool calling | A pergunta de seguimento e o pedido anterior fundido com a resposta do utilizador. Não usei tool calling nem agent loop: o fluxo tem passos fixos, e o Python escolhe o caminho | `workflow.py`, `llm/write_followup.py` |
| 7 | Agentes e FastAPI | Controlo na aplicação, não no modelo: limites e regras em Python, falhas tratadas como dados, trace por chamada, histórico em SQLite. Não usei FastAPI: o `service.py` faz de camada de serviço e a interface é Streamlit | `service.py`, `storage/db.py` |

Requisitos mínimos do projeto: mais de dois passos com LLM (3), saída estruturada validada, comportamento definido quando falta informação, e um conjunto de casos de teste.

## Aprendizagem contínua: medir, mudar, voltar a medir

A sessão 5 diz que uma alteração só conta depois da comparação. Foi assim que o projeto evoluiu: cada alteração foi medida nos mesmos casos.

- **Primeira avaliação (`dev`): 23/31.** Falhas diagnosticadas por passo (extração, retrieval ou resumo) antes de mexer em qualquer coisa.
- **Depois de várias iterações nos prompts e na recuperação: 31/31.** Uma alteração de cada vez, mantendo o resto igual.
- **Cinco casos novos de dados em falta** (pergunta de seguimento): `dev` com **36/36**, recall 1,00, perguntas do modelo válidas 7/7.
- **Estabilidade:** 3 execuções seguidas do `dev`, todas 36/36, com os mesmos tokens de entrada. As decisões são estáveis; só a redação do resumo varia.
- **Prompt do resumo `v3` → `v4`:** o caso `amend-manutencao-urgente` errava a comparação de limites em 2 de 3 execuções com a `v3`, e em 0 de 5 com a `v4`.
- **`holdout`: 14/14.** Aviso honesto: este conjunto já tinha sido visto uma vez, quando tinha dado 10/14 numa versão inicial. Por isso mostra que os prompts congelados generalizam para estes 14 casos, mas não é uma validação cega.

Custo: cerca de 0,001 $ por caso, 2 a 3 chamadas ao LLM por pedido (3 se faltarem dados). Estimativa feita com os preços configurados em `PRICES_PER_MILLION`, em `eval/run_eval.py`.

## Casos de teste

- **Avaliação (50 casos):** pedidos completos, dados em falta, dados inválidos, prompt injection (e pedidos legítimos que parecem injection), cláusulas com e sem cobertura, emendas à política e casos ambíguos. 36 em `dev` e 14 em `holdout`.
- **Testes (47):** validação, escalões (999,99 / 1000 / 5000 / 5000,01), citações, fusão de pedidos, pergunta de seguimento, base de dados e o fluxo completo com o LLM substituído por respostas fixas.

## Comportamento seguro

| Situação | Resultado |
|---|---|
| Tentativa de manipulação | Rejeitado, nada é gravado |
| Faltam dados | `needs_info`, com pergunta |
| Dados inválidos (quantidade ou valor ≤ 0) | Rejeitado |
| Mais de 5 000 € | Ação manual |
| Política sem cláusula relevante, ou erro na consulta | Ação manual |
| Resumo com citação inventada | Sem resumo; a decisão mantém-se |

## Limitações conhecidas

- A validação das citações confirma que o id existe, não que a frase está de acordo com a cláusula. A fidelidade do resumo foi conferida à mão. Exemplo observado: em embalagens de 1 000 €, o resumo disse que a cláusula 2.2 "é substituída pela 8.2", quando a 8.2 só altera a 5.6.
- 50 casos dão uma indicação, não uma garantia. O `holdout` é pequeno e já foi visto uma vez.
- Os pedidos suspeitos não ficam registados e não há contador de tentativas por sessão.
- Não implementei pesquisa híbrida (lexical + semântica) nem uma comparação com um baseline sem RAG.

## Estrutura

```
app/streamlit_app.py     interface
scripts/                 run.py, build_index.py
src/pr_triage/
  workflow.py            os 7 passos
  service.py             camada de serviço (pedidos e histórico)
  domain/                schemas, validação, escalões, estados, citações
  llm/                   chamadas ao modelo e prompts versionados
  rag/                   índice e recuperação
  storage/db.py          SQLite
data/policies/           8 documentos, 47 cláusulas
data/eval/cases.jsonl    casos de avaliação
eval/run_eval.py         avaliação e métricas
tests/
```

Cada pedido (exceto os suspeitos) fica em `pr_triage.db` (SQLite, ignorado pelo Git), com o resultado completo em JSON: evidência, resumo, pergunta e, por chamada, a versão do prompt e os tokens.
