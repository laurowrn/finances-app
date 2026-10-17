from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import close_client, ensure_indexes
from app.routers import (
    ai,
    auth,
    categories,
    imports,
    payments,
    reports,
    rules,
    transactions,
    users,
)
from app.seed import seed_if_empty
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    await seed_if_empty()
    yield
    close_client()


app = FastAPI(title="Group Finance API", version="0.1.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ai.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(rules.router)
app.include_router(imports.router)
app.include_router(transactions.router)
app.include_router(payments.router)
app.include_router(reports.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "ai_enabled": settings.ai_enabled}
