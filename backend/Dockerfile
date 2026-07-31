FROM python:3.12-slim

# uv para instalar dependências
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# o build do pacote precisa do código-fonte presente
COPY pyproject.toml ./
COPY app ./app

RUN uv pip install --system --no-cache .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
