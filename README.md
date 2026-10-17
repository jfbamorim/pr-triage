# Triagem de requisições de compra

Assistente de triagem para pedidos de compra (Purchasing / P2P). O utilizador descreve o pedido em texto livre; a aplicação extrai os dados, valida-os, determina o escalão de valor e consulta a política de compras. Devolve uma de três saídas: sem bloqueios, política a verificar, ou ação manual.

O LLM nunca aprova nada: só lê, extrai e explica. As decisões são código Python determinístico, e a aprovação continua a ser humana.

Projeto final do curso "Generative AI: Fundamentos e Aplicação" (EDIT).

## Para quem avalia

**Executar, depois de clonar ou fazer pull:**

```bash
uv sync
cp .env.example .env        # preencher OPENAI_API_KEY
uv run python scripts/run.py
```

O `run.py` constrói o índice da política na primeira execução (poucos segundos, uma chamada de embeddings) e depois abre a interface em `http://localhost:8501`. Nas execuções seguintes reutiliza o índice; `--rebuild` obriga a reconstruí-lo. A interface tem 3 exemplos de pedidos para experimentar. É preciso uma chave da OpenAI, porque todos os passos com modelo e as embeddings usam a API (cerca de 0.001 $ por pedido).

**Sem chave, dá para ver:** `uv run pytest -q` (30 testes, sem API) e os resultados guardados em `eval/results/`.

**Onde investi mais tempo: RAG e avaliação.**

- **RAG.** O corpus tem 8 documentos e 47 cláusulas, com emendas que alteram cláusulas anteriores e lacunas intencionais para testar a abstenção. A recuperação foi o que mais iterei: query com a categoria do item, cláusulas obrigatórias juntadas por id (escalão, urgência, contrato-quadro), ligação das emendas às cláusulas que alteram e um limiar de similaridade que se manteve fixo em vez de ser baixado para fazer casos passar. Isto levou o `dev` de 23/31 para 31/31 (ver "Avaliação").
- **Avaliação.** 50 casos etiquetados, separados em `dev` (afinar) e `holdout` (correr uma vez, no fim, sem afinar). Os valores esperados nunca foram alterados para ajustar aos resultados. Cada execução regista tokens, custo e latência por passo, e a versão de cada prompt, por isso cada ficheiro em `eval/results/` é reproduzível e comparável. Foi a avaliação que mostrou os problemas reais (por exemplo, categorias mal atribuídas que arrastavam cláusulas erradas) e que obrigou a corrigir a extração em vários passos, de `extraction-v3` a `v5`.
- **O resto** (interface, persistência) é deliberadamente simples.

## Problema e utilizador

Pedidos de compra chegam incompletos ou mal descritos, e quem os trata tem de conferir à mão regras de cotações e escalões espalhadas por vários documentos.

- **Utilizador:** quem faz o pedido, em texto livre.
- **Destinatário:** a equipa de Compras, que recebe pedidos triados, com a evidência da política à vista e um resumo que cita as cláusulas.

## Princípios

1. **O LLM propõe, o Python decide.** Estado, escalão e escalação são código determinístico.
2. **Falha segura.** Em caso de dúvida ou erro, o pedido vai para uma pessoa; nunca se assume que "não há regra".
3. **Rastreável.** Cada resposta mostra a evidência da política, as cláusulas citadas, a versão de cada prompt e os tokens gastos.

## Fluxo

![Fluxo](docs/fluxo.png)

1. **Verificar o texto** (LLM): deteta tentativas de manipular o sistema. Texto suspeito, ou falha neste passo, rejeita o pedido.
2. **Extrair os dados** (LLM): item, quantidade, valor estimado, centro de custo, categoria, urgência e menção a contrato-quadro, com saída validada por schema (Pydantic). O resultado é fundido com o pedido anterior, se existir.
3. **Validar** (Python): dados em falta dão `NEEDS_INFO`; dados inválidos dão `REJECTED`.
4. **Determinar o escalão** (Python): abaixo de 1 000 €, de 1 000 a 5 000 € (inclusive) ou acima de 5 000 €.
5. **Consultar a política** (RAG): pesquisa por similaridade sobre as cláusulas, mais as cláusulas que o pedido obriga a incluir.
6. **Decisão** (Python): sem bloqueios, política a verificar, ou ação manual.
7. **Resumo com citações** (LLM + Python): texto em português sobre o que a política exige, com os `chunk_id` das cláusulas em que se baseia. Se citar uma cláusula que não foi recuperada, ou não citar nenhuma, o resumo é descartado e a decisão mantém-se.

## Comportamento quando falta informação ou há risco

| Situação | Resultado |
|---|---|
| Faltam dados | `NEEDS_INFO`. O LLM escreve uma pergunta que pede só o que falta; o Python valida que cada campo em falta é mencionado e, se não for, usa uma frase fixa. O utilizador responde na mesma caixa e a resposta é fundida com o pedido anterior (o dado novo prevalece; categoria e flags persistem). Só pedidos em `NEEDS_INFO` aceitam respostas de seguimento. |
| Dados inválidos | `REJECTED` (`INVALID_DATA`) |
| Texto suspeito, ou falha do screening | `REJECTED` (`SUSPICIOUS_ACTIVITY`) |
| Valor acima de 5 000 € | Ação manual (`OVER_THRESHOLD`) |
| Nenhuma cláusula relevante na política | Ação manual (`NO_POLICY_EVIDENCE`) |
| Erro na consulta da política | Ação manual (`RETRIEVAL_ERROR`) |
| Resumo com citações inválidas | Sem resumo; a decisão não muda |

## Política de compras (RAG)

`data/policies/` contém um corpus fictício de 8 documentos e 47 cláusulas, com emendas (`08`) que alteram cláusulas anteriores e lacunas intencionais (por exemplo, licenças de software ou leasing), para testar a abstenção.

- **Chunking:** uma cláusula por chunk, com o prefixo `Documento | Cláusula | Título` no texto e metadados (`source`, `clause`, `title`, `effective_date`, `amends`, `chunk_id`).
- **Embeddings:** `text-embedding-3-small`, guardados em Chroma (distância cosseno).
- **Query:** `"<termo da categoria>: compra de <item>"`, por exemplo "mobiliário e material de escritório: compra de cadeiras". A categoria vem da extração (lista fechada). Se for `other`, a query é só `Compra de <item>`.
- **Seleção:** `MIN_SCORE = 0.52` e no máximo 6 cláusulas. O limiar não foi baixado para fazer casos passar.
- **Cláusulas juntadas por id:** a do escalão (2.1, 2.2 ou 2.3); as emendas que alteram uma cláusula recuperada (via `amends`); a 2.4 (compras urgentes) quando o pedido é urgente e o escalão não é o mais baixo; a 3.2 (contrato-quadro) quando o pedido o menciona.

## Avaliação

`data/eval/cases.jsonl` tem 50 casos etiquetados, repartidos por grupos (fronteiras de escalão, dados em falta e inválidos, injeção, injeção legítima, cobertura, sem cobertura, emendas, ambíguos, urgência). Cada caso tem o resultado esperado (estado, razão, escalão, escalação, campos em falta ou inválidos, cláusulas que a evidência tem de incluir).

- **`dev`** (36 casos): serve para afinar prompts e recuperação.
- **`holdout`** (14 casos): corre-se uma vez, no fim, e nunca se afina com ele.

```bash
uv run python eval/run_eval.py --split dev --out eval/results/dev.json
uv run python eval/run_eval.py --split dev --group missing
```

Cada execução imprime a versão dos quatro prompts, os totais por grupo, o recall das cláusulas esperadas, os resumos e as perguntas válidos, a latência e uma tabela de tokens e custo estimado por passo.

**Evolução no `dev`** (os valores esperados nunca foram alterados para ajustar aos resultados):

| Alteração | Casos certos |
|---|---|
| Base: query só com o item | 23/31 |
| Categoria na query, cláusulas 2.4 e 3.2 forçadas | 27/31 |
| Definições de categoria (software e leasing são `other`) | 31/31 |
| Item sem a quantidade (`extraction-v5`), follow-up e métricas | 36/36 (31 + 5 novos de dados em falta) |

Última execução do `dev` (36 casos): recall médio das cláusulas 1.00, 24/24 resumos válidos, 7/7 perguntas do modelo válidas, latência média 3.6 s, cerca de 0.001 $ por caso. Os ficheiros de cada passo estão em `eval/results/`.

<!-- Holdout: correr uma vez no fim e escrever aqui o resultado. -->

### Prompts versionados

| Prompt | Versão |
|---|---|
| Screening | `screening-v3` |
| Extração | `extraction-v5` |
| Resumo | `summary-v3` |
| Pergunta de seguimento | `followup-v1` |

A versão é registada em cada chamada ao modelo e impressa no eval, por isso cada ficheiro de resultados diz com que prompts foi gerado. Qualquer alteração a um prompt sobe a versão e obriga a voltar a correr o `dev`.

### Custo e preços

O custo estimado usa os preços por milhão de tokens em `PRICES_PER_MILLION` (`eval/run_eval.py`): `gpt-4.1-mini` 0.40 $ de entrada e 1.60 $ de saída, `text-embedding-3-small` 0.02 $. <!-- Confirmar os preços antes da entrega. -->

## Testes

```bash
uv run pytest -q
```

Cobrem o que o Python decide, sem chamar a API: validação, estado, limites dos escalões, validação de citações (rejeita ids inventados), fusão de pedidos e o validador da pergunta de seguimento.

## Estrutura

```
app/streamlit_app.py       interface (passos em direto, pergunta, resultado, evidência)
data/policies/             corpus de políticas (markdown)
data/eval/cases.jsonl      casos de avaliação
eval/run_eval.py           corre os casos e mede qualidade, tokens e custo
scripts/run.py             constrói o índice (se faltar) e arranca a interface
scripts/build_index.py     cria o índice Chroma
src/pr_triage/
  domain/                  schemas, estados, escalões, validação, fusão, citações, follow-up
  llm/                     screening, extração, resumo, pergunta (OpenAI Responses API) e métricas
  rag/                     chunking, índice, query, pesquisa, seleção de contexto
  storage/db.py            SQLite
  workflow.py              fluxo por passos (emite um evento por passo)
  service.py               fluxo + persistência
tests/                     testes unitários
```

Cada pedido (exceto os suspeitos) fica registado em `pr_triage.db` (SQLite, ignorado pelo Git), com categoria, urgência e menção a contrato-quadro, para a conversa de seguimento.

Alternativa ao `run.py`, em dois passos: `uv run python scripts/build_index.py` e `uv run streamlit run app/streamlit_app.py`.

## Limitações conhecidas

- **O modelo não é determinístico**, nem com `temperature=0`: a extração do mesmo texto e a fidelidade do resumo variam entre execuções.
- **A validação das citações só confirma que os ids existem**, não que o texto do resumo seja fiel à cláusula. Exemplo observado: no caso `amend-manutencao-urgente` (4 000 €, urgente), o resumo diz que a cláusula 2.4 não se aplica "acima de 5 000 €", quando o pedido está abaixo desse valor. A fidelidade foi conferida à mão.
- **O termo de pesquisa de `investment_goods`** traz por vezes cláusulas não relacionadas (3.6, 8.4, 2.3) para outros itens.
- **A margem do limiar de similaridade é curta** em alguns casos (por exemplo, 0.514 contra 0.52).
- **Os casos de avaliação são poucos** (50): 36/36 no `dev` significa que não há regressões conhecidas, não que o sistema generalize.
- **Não há contador de tentativas suspeitas por sessão**, e a evidência e o resumo não são persistidos.