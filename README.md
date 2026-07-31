# Finanças do Casal 💸

App de gestão de finanças em grupo (casal). Importa gastos de extratos **OFX/CSV/PDF**,
classifica **por regras** (com ajuda opcional de IA para criar as regras), e gera o
**relatório mensal** com quem gastou mais e o **acerto proporcional ao salário**.

Substitui a planilha manual: cada um loga (ou importa) os gastos, marca o que é
**compartilhado** ou **individual**, e o app calcula quanto um deve pagar ao outro.

## Como funciona o acerto

- Só gastos **compartilhados** entram no acerto.
- Cada um deveria arcar proporcional ao salário: `cota = (salário / soma dos salários) × total compartilhado`.
- `saldo = quanto pagou de compartilhado − cota justa`. Quem pagou menos que a cota paga a diferença ao outro.
- Gastos **individuais** contam só no "quem gastou mais", fora do acerto.

## Stack

- **Backend**: FastAPI + MongoDB (Motor), Python 3.12, uv, pytest.
- **Frontend**: Vite + React 19 + TypeScript, Tailwind v4, TanStack Query, Recharts.
- **Local**: docker-compose (mongo + backend + frontend).

## Rodando com Docker (recomendado)

```bash
cp .env.example .env   # ajuste nomes, salários e (opcional) ANTHROPIC_API_KEY
docker compose up --build
```

- Frontend: http://localhost:3009
- API/docs: http://localhost:8000/docs
- O backend **cria índices e faz o seed** (2 usuários + categorias) no primeiro start.
- Login: escolha o usuário e use a senha de `LOGIN_PASSWORD` (padrão `casal`).

## Rodando o backend localmente (sem Docker)

Precisa de um Mongo rodando (`docker compose up mongo`).

```bash
cd backend
make setup     # cria .venv e instala deps (via uv)
make seed      # cria usuários + categorias
make run       # uvicorn em :8000
make test      # pytest
```

## Rodando o frontend localmente

```bash
cd frontend
npm install
npm run dev    # http://localhost:3009  (usa VITE_API_BASE, padrão http://localhost:8000)
```

## Fluxo de uso

1. **Configurações** → confira nomes e salários (base e, se quiser, ajuste por mês).
2. **Importar** → suba um OFX/CSV/PDF e escolha o titular. Débitos viram gastos; duplicados são ignorados.
3. **Regras** → clique em **Sugerir regras**: os gastos sem categoria são agrupados por
   estabelecimento. Com `ANTHROPIC_API_KEY`, o Claude pré-preenche categoria/divisão;
   sem chave, você escolhe manualmente. Aceitar cria uma **regra** e reclassifica.
4. **Gastos** → ajuste categoria e compartilhado/individual, ou lance um gasto manual.
5. **Relatório** → veja quem gastou mais, o breakdown por categoria e o **acerto do mês**.

> A partir daí, novas importações são classificadas **só por regras** — sem custo de IA.

## Classificação: regras primeiro, IA só no bootstrap

O motor de classificação é **determinístico** (`backend/app/services/classifier.py`):
regras por prioridade, primeira que casar vence. A IA (`services/ai.py`) é opcional e
serve apenas para **propor** regras a partir dos gastos ainda sem categoria — você revisa
e aceita. Sem `ANTHROPIC_API_KEY`, tudo funciona com regras + classificação manual.

## Parsers de extrato

- **OFX** (`ofxparse`): mais confiável — prefira exportar OFX do banco.
- **CSV**: detecta separador e decimal PT-BR; escolhe débitos (extrato) ou compras (fatura) por heurística.
- **PDF** (`pdfplumber`): melhor esforço, marque para revisão.

> Os parsers foram calibrados com exemplos genéricos (ver `backend/tests/fixtures/`).
> Para os seus bancos, coloque 1 arquivo real de cada tipo e ajuste os adapters em
> `backend/app/services/parsers/`.

## Testes

`cd backend && make test` — cobre o cálculo do acerto (`test_settlement.py`), o rule engine,
o dedup, os parsers, e um teste de integração do endpoint de relatório.
