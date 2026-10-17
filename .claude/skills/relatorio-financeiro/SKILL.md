---
name: relatorio-financeiro
description: Gera o "Relatório IA" mensal do finances-app — analisa os gastos de um mês, revisa se as metas do mês anterior foram cumpridas e cria novas metas SMART para o mês seguinte, gravando tudo via API. Use quando o usuário pedir análise dos gastos, relatório do mês, metas de economia, "como foi o mês", ou acompanhamento das metas. Também quando fechar um mês e ele quiser saber onde economizar.
---

# Relatório financeiro mensal

Você é o motor de análise do app. O backend fornece os números já somados e é
quem julga se uma meta foi cumprida; você escreve a interpretação e propõe as
metas do próximo mês.

**A regra que organiza tudo:** você nunca recalcula um total. Se um número
aparece no dossiê, use-o como está. Se precisar de um número que o dossiê não
tem, prefira dizer que não tem a estimá-lo.

## 1. Autenticar

O app roda em `http://localhost:8000`. A senha está no `.env` do projeto
(`LOGIN_PASSWORD`, padrão `casal`).

```bash
cd <raiz-do-projeto>
UID=$(curl -s localhost:8000/auth/users | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
PW=$(grep '^LOGIN_PASSWORD=' .env | cut -d= -f2)
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$UID\",\"password\":\"$PW\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

Use `-H "Authorization: Bearer $TOKEN"` em todas as chamadas. Se o backend não
responder, avise o usuário para subir com `docker compose up -d` — não invente
números nem leia o Mongo direto.

## 2. Endpoints

| Método | Rota | Para quê |
|---|---|---|
| GET | `/ai/analysis/{period}` | **O dossiê.** Tudo que a análise precisa, pré-agregado |
| GET | `/ai/reports` | Lista os relatórios já gravados |
| GET | `/ai/reports/{period}` | Um relatório (inclui as metas) |
| GET | `/ai/reports/{period}/progress` | **Julga as metas** daquele relatório contra os dados reais |
| POST | `/ai/reports` | Grava o relatório novo |
| DELETE | `/ai/reports/{period}` | Apaga |

`period` é `"YYYY-MM"`. Todo valor monetário é **inteiro de centavos**
(`amount_cents`, `target_cents`, …) — `123456` é R$ 1.234,56. Nunca envie
decimal.

`/ai/reports/{period}/progress` aceita `?against=YYYY-MM` para conferir contra
outro mês; sem isso avalia o `goals_period` do próprio relatório.

## 3. O procedimento

### a) Ler o dossiê do mês a analisar

```bash
curl -s "localhost:8000/ai/analysis/2026-07" -H "Authorization: Bearer $TOKEN"
```

Ele traz: total e contagem, o que foi **ignorado** (fatura de cartão,
transferências entre contas), renda e % da renda gasta, sobra, gasto por
pessoa, categorias com histórico de 5 meses e média, top merchants com ticket
médio, recorrentes (Assinaturas/Academia/Internet), parcelas em aberto com a
cauda comprometida, os 15 maiores lançamentos, série mensal e o acerto do mês.

**Leia `data_warnings` e repasse ao usuário o que estiver lá** (ex.: mês sem
renda cadastrada). Se `transaction_count` for 0, pare e avise — não há o que
analisar.

### b) Revisar as metas do mês anterior — se existirem

```bash
curl -s localhost:8000/ai/reports -H "Authorization: Bearer $TOKEN"
curl -s "localhost:8000/ai/reports/2026-06/progress" -H "Authorization: Bearer $TOKEN"
```

O campo `achieved` é do servidor, não seu: **não rediscuta se a meta foi
cumprida**. Seu trabalho é explicar *por que* — e uma meta estourada merece
diagnóstico honesto, não desculpa. Escreva isso em `previous_review_md`.

Se uma meta falhou por ser irreal e não por comportamento, diga, e proponha a
próxima com alvo mais folgado. Repetir a mesma meta impossível não ajuda.

### c) Escrever o relatório (`summary_md`)

Markdown. O renderizador do app suporta títulos, listas, tabelas, citação,
`**negrito**`, `*itálico*` e `` `código` `` — nada além disso.

Estrutura que funciona:

1. **Abertura de um parágrafo** com o número que importa: total, % da renda,
   sobra, e como se compara com a média dos meses anteriores.
2. **Ressalvas de dados**, se houver. Mês incompleto, categoria nova que
   quebra a comparação histórica, extrato faltando. Isso vem antes das
   conclusões — um número mal comparado contamina todo o resto.
3. **Tabela de onde o dinheiro foi**, as categorias que importam.
4. **Onde cortar**, em seções. Cada uma com: o achado, o número, o impacto
   mensal e anual, e a ressalva de quando não vale.
5. **Tabela de impacto**, separando o que é decisão (cancelar algo) do que
   depende de mudança de hábito. São coisas de dificuldade muito diferente.
6. **O que não mexer** — aluguel, contas, impostos. Dizer isso evita que o
   usuário procure economia onde não tem.

Padrões que costumam render:

- **Serviços redundantes** — duas academias, dois streamings da mesma coisa.
- **Cobrança duplicada** — mesmo valor, mesmo dia, mesmo fornecedor.
- **Alta frequência com ticket baixo** — muitas idas ao mercado/conveniência.
  A frequência é o gasto, não o ticket.
- **Cauda de parcelamento** — quanto dos próximos meses já está comprometido.
- **Categoria muito acima da própria média** (`average_cents` no dossiê).

### d) Propor as metas

**Só metas que o servidor consegue medir.** Quatro métricas:

| `metric` | Campos | Mede |
|---|---|---|
| `category_max` | `category_id`, `target_cents` | Gasto na categoria ≤ alvo |
| `merchant_max` | `match`, `target_cents` | Gasto cuja descrição contém `match` ≤ alvo |
| `total_max` | `target_cents` | Gasto total do mês ≤ alvo |
| `count_max` | `match` e/ou `category_id`, `target_count` | Nº de lançamentos ≤ alvo |

`match` é comparado normalizado (sem acento, sem caixa, sem pontuação), igual
ao motor de regras: `"cooper"` casa `"Cooper Filial Itoupava"`.

Sempre preencha `baseline_cents` (ou `baseline_count`) com o valor do mês
analisado — é dele que sai o "economizou X" e o gráfico de progresso.

Regras para as metas serem boas:

- **3 a 5 metas.** Mais que isso ninguém acompanha.
- **Alvo derivado do dado, não redondo por estética.** Corte de 10–25% sobre o
  baseline é exigente e possível; 50% é fantasia e desmotiva.
- **Pelo menos uma que dependa só de uma decisão** (cancelar assinatura), para
  o mês começar com uma vitória garantida.
- **No máximo uma `total_max`.** Ela se sobrepõe às outras; use como teto geral.
- **Nada de meta sobre gasto fixo** (aluguel, condomínio, imposto).
- `id` em kebab-case e estável entre meses quando for a mesma meta
  (`mercado-cooper`), para dar para comparar a evolução.
- O `rationale` explica *por que esse alvo* — ele aparece na tela, embaixo do
  título.

### e) Gravar

```bash
curl -s -X POST localhost:8000/ai/reports -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d @relatorio.json
```

```json
{
  "period": "2026-07",
  "goals_period": "2026-08",
  "summary_md": "# Julho/2026\n...",
  "previous_review_md": "As metas de junho...",
  "generated_by": "claude-code",
  "goals": [
    {
      "id": "assinaturas",
      "title": "Assinaturas até R$ 90",
      "metric": "category_max",
      "category_id": "6a6df686ef9897441f1c1beb",
      "target_cents": 9000,
      "baseline_cents": 15214,
      "rationale": "Cancelar o Amazon Ad Free e baixar o plano do Disney+ já chega lá."
    },
    {
      "id": "idas-mercado",
      "title": "No máximo 6 idas ao Cooper",
      "metric": "count_max",
      "match": "cooper",
      "target_count": 6,
      "baseline_count": 12,
      "rationale": "Foram 12 idas em julho; concentrar em uma por semana corta a compra por impulso."
    }
  ]
}
```

Gravar o mesmo `period` **substitui** o anterior. Os `category_id` vêm de
`GET /categories` ou do próprio dossiê.

Depois de gravar, confira que ficou consistente:

```bash
curl -s "localhost:8000/ai/reports/2026-07/progress" -H "Authorization: Bearer $TOKEN"
```

### f) Fechar com o usuário

Diga onde ver (aba **Relatório IA**), resuma as metas em uma linha cada e o
impacto total esperado. Se você deixou algo de fora por incerteza, fale.

## Erros que valem evitar

- **Comparar categoria com mês anterior sem checar se ela existia.** Categoria
  criada há pouco tem histórico zerado, e a "queda" é artefato de
  reclassificação. O dossiê traz `history_cents` por mês — se os anteriores
  forem 0 e o atual não, desconfie antes de comemorar.
- **Contar como gasto o que está em `ignored_cents`.** Pagamento de fatura e
  transferência entre contas do casal já saem do total; mencioná-los como
  economia possível é erro.
- **Meta em cima de gasto que não se repete.** Uma latoaria de R$ 4.000 num mês
  não vira meta de corte no mês seguinte.
- **Arredondar centavos.** Os valores são inteiros; `formatBRL` é problema do
  frontend.
