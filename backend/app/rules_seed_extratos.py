"""Regras de categorização derivadas dos extratos de julho/2026.

    python -m app.rules_seed_extratos           # simula contra os extratos
    python -m app.rules_seed_extratos --apply   # grava as regras no Mongo

Convenção de prioridade (menor = ganha primeiro):
    20  merchant específico visto no extrato
    50  padrão genérico forte (ex.: "farmacia", "estacionamento")
    60  padrão genérico amplo (ex.: "uber", "cinema")

Regras com split IGNORED tiram o lançamento do relatório sem apagá-lo. É o que
resolve a sobreposição entre o extrato da conta e a fatura do cartão: o
"Pagamento de fatura" no extrato é a mesma despesa das compras da fatura.
"""

import argparse
import asyncio
from pathlib import Path

from app.db import close_client, get_db
from app.models.enums import MatchOp, Split
from app.repositories import categories as cat_repo
from app.repositories import rules as rules_repo
from app.repositories.common import oid
from app.services.classifier import Rule, classify
from app.services.money import format_brl
from app.services.parsers import parse_file

# Categorias criadas por este script se ainda não existirem.
NEW_CATEGORIES = [
    {"name": "Pet", "icon": "dog", "is_shared_default": True},
    {"name": "Compras/Marketplace", "icon": "shopping-bag", "is_shared_default": True},
    # Toda regra precisa de uma categoria; as de ignorar apontam para esta, que
    # serve de rótulo na lista de gastos. Nada aqui entra no relatório.
    {"name": "Ignorado", "icon": "eye-off", "is_shared_default": False},
]

# Regras de rodadas anteriores que foram substituídas por versões melhores.
# Removidas no --apply para não ficar lixo no banco.
OBSOLETE: list[tuple[MatchOp, str]] = [
    (MatchOp.CONTAINS, "farmacia"),  # -> "farmaci" (pega descrição truncada)
    (MatchOp.CONTAINS, "drogaria"),  # -> "drogari"
]

# (categoria, op, valor, prioridade, split)
# split=None -> usa o is_shared_default da categoria
RULES: list[tuple[str, MatchOp, str, int, Split | None]] = [
    # ---------- Mercado ----------
    # Atenção: NADA de regra com "mercado" solto — casaria "Mercado Livre",
    # que é marketplace, não supermercado.
    ("Mercado", MatchOp.CONTAINS, "cooper filial", 20, None),
    ("Mercado", MatchOp.CONTAINS, "bistek", 20, None),
    ("Mercado", MatchOp.CONTAINS, "supermercado", 50, None),
    ("Mercado", MatchOp.CONTAINS, "hipermercado", 50, None),
    ("Mercado", MatchOp.CONTAINS, "atacadao", 50, None),
    ("Mercado", MatchOp.CONTAINS, "angeloni", 50, None),
    ("Mercado", MatchOp.CONTAINS, "giassi", 50, None),
    # ---------- Restaurante/Delivery ----------
    # "Ifd*" é o prefixo do iFood nas faturas de cartão.
    ("Restaurante/Delivery", MatchOp.CONTAINS, "ifd", 50, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "ifood", 50, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "rappi", 50, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "basilic friggitoria", 20, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "lanchonete", 50, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "restaurante", 50, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "pizzaria", 50, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "churrascaria", 50, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "padaria", 50, None),
    # ---------- Transporte ----------
    ("Transporte", MatchOp.CONTAINS, "uberrides", 20, None),
    ("Transporte", MatchOp.CONTAINS, "uber", 60, None),
    ("Transporte", MatchOp.CONTAINS, "estacionamento", 50, None),
    ("Transporte", MatchOp.CONTAINS, "99app", 50, None),
    # ---------- Gasolina ----------
    ("Gasolina", MatchOp.CONTAINS, "posto bela joia", 20, None),
    ("Gasolina", MatchOp.CONTAINS, "auto posto", 50, None),
    ("Gasolina", MatchOp.CONTAINS, "ipiranga", 50, None),
    ("Gasolina", MatchOp.CONTAINS, "petrobras", 50, None),
    # ---------- Farmácia ----------
    # Prioridade 15 (abaixo dos merchants p=20) de propósito: "Cooper Filial
    # Farmaci" casa "cooper filial" (Mercado) e "farmaci" — a farmácia ganha.
    # "farmaci" sem o "a" final porque o extrato trunca a descrição.
    ("Farmácia", MatchOp.CONTAINS, "farmaci", 15, None),
    ("Farmácia", MatchOp.CONTAINS, "drogari", 15, None),
    ("Farmácia", MatchOp.CONTAINS, "drogasil", 15, None),
    ("Farmácia", MatchOp.CONTAINS, "panvel", 15, None),
    # "raia" solto casaria "praia"; o regex exige Droga Raia ou Raia<loja>.
    ("Farmácia", MatchOp.REGEX, r"(droga\s?raia|\braia\d+)", 25, None),
    # ---------- Assinaturas ----------
    ("Assinaturas", MatchOp.CONTAINS, "netflix", 20, None),
    ("Assinaturas", MatchOp.CONTAINS, "disney plus", 20, None),
    ("Assinaturas", MatchOp.CONTAINS, "hbomax", 20, None),
    ("Assinaturas", MatchOp.CONTAINS, "amazonprime", 20, None),
    ("Assinaturas", MatchOp.CONTAINS, "amazon prime", 20, None),
    ("Assinaturas", MatchOp.CONTAINS, "amazon ad free", 20, None),
    ("Assinaturas", MatchOp.CONTAINS, "spotify", 20, None),
    ("Assinaturas", MatchOp.CONTAINS, "youtube premium", 20, None),
    # ---------- Academia ----------
    ("Academia", MatchOp.CONTAINS, "intent gym", 20, None),
    # Wellhub vem com o nome de uma pessoa só na descrição -> individual.
    ("Academia", MatchOp.CONTAINS, "wellhub", 20, Split.INDIVIDUAL),
    ("Academia", MatchOp.CONTAINS, "gympass", 50, None),
    ("Academia", MatchOp.CONTAINS, "smart fit", 50, None),
    # ---------- Luz ----------
    ("Luz", MatchOp.CONTAINS, "celesc", 20, None),
    # ---------- Aluguel / moradia ----------
    ("Aluguel", MatchOp.CONTAINS, "conexao estrategia imobiliaria", 20, None),
    ("Aluguel", MatchOp.CONTAINS, "cond ed bergamo", 20, None),
    # ---------- Lazer ----------
    ("Lazer", MatchOp.CONTAINS, "arcoplexcinemas", 20, None),
    ("Lazer", MatchOp.CONTAINS, "cinema", 60, None),
    ("Lazer", MatchOp.CONTAINS, "cinemark", 50, None),
    # ---------- Internet ----------
    ("Internet", MatchOp.CONTAINS, "vivo fibra", 50, None),
    ("Internet", MatchOp.CONTAINS, "claro net", 50, None),
    ("Internet", MatchOp.CONTAINS, "unifique", 50, None),
    # "Débito em conta" são os dois débitos automáticos de internet (fibra e
    # móvel). EQUALS, não CONTAINS: a descrição é genérica do banco e qualquer
    # outro débito automático futuro NÃO deve cair aqui sem revisão.
    ("Internet", MatchOp.EQUALS, "Débito em conta", 20, None),
    # ---------- Pet ----------
    ("Pet", MatchOp.CONTAINS, "pet shop", 20, None),
    ("Pet", MatchOp.CONTAINS, "agro aves", 20, None),
    ("Pet", MatchOp.CONTAINS, "petz", 50, None),
    ("Pet", MatchOp.CONTAINS, "cobasi", 50, None),
    # ---------- Compras/Marketplace ----------
    ("Compras/Marketplace", MatchOp.CONTAINS, "mercadolivre", 30, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "mercado livre", 30, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "amazonmktplc", 30, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "amazon marketplace", 30, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "intheboxcom", 30, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "havan", 30, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "shopee", 50, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "aliexpress", 50, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "magazine luiza", 50, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "magalu", 50, None),
    # ---------- Lazer (pizzaria Tarthurell) ----------
    # "tarthurel" (sem o L final) casa as duas grafias que aparecem.
    ("Lazer", MatchOp.CONTAINS, "tarthurel", 20, None),
    # ---------- Outros: impostos ----------
    ("Outros", MatchOp.CONTAINS, "sefaz", 30, None),
    ("Outros", MatchOp.CONTAINS, "receita federal", 30, None),
    ("Outros", MatchOp.CONTAINS, "detran", 30, None),
    # ---------- Outros: Pix como último recurso ----------
    # Prioridade alta de propósito: qualquer Pix com merchant conhecido (cinema,
    # restaurante, ou o Pix ignorado para a Nayara) casa antes e ganha.
    ("Outros", MatchOp.CONTAINS, "transferencia enviada pelo pix", 90, None),
    # ---------- Ignorar ----------
    # Fatura do cartão: a despesa real vem pelo arquivo da fatura.
    ("Ignorado", MatchOp.CONTAINS, "pagamento de fatura", 10, Split.IGNORED),
    # Aplicação financeira: sai da conta mas continua sendo patrimônio.
    ("Ignorado", MatchOp.CONTAINS, "aplicacao rdb", 10, Split.IGNORED),
    # Transferência entre o casal: acerto, não gasto (ver tela de Pagamentos).
    ("Ignorado", MatchOp.CONTAINS, "nayara paola teixeira", 10, Split.IGNORED),
    # ================= 2ª rodada: fatura de agosto + cartão da Nayara =========
    # ---------- Qtal (minimercado; categoria já existia da planilha) ----------
    ("Qtal", MatchOp.CONTAINS, "qtal", 20, None),
    # ---------- Mercado ----------
    ("Mercado", MatchOp.CONTAINS, "carrefour", 30, None),
    ("Mercado", MatchOp.CONTAINS, "assai", 50, None),
    ("Mercado", MatchOp.CONTAINS, "minimercado", 55, None),
    # ---------- Restaurante/Delivery ----------
    ("Restaurante/Delivery", MatchOp.CONTAINS, "chiquinho sorvetes", 20, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "officina cafe", 20, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "sorveteria", 50, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "sorvetes", 50, None),
    ("Restaurante/Delivery", MatchOp.CONTAINS, "cafeteria", 50, None),
    # ---------- Assinaturas ----------
    ("Assinaturas", MatchOp.CONTAINS, "google one", 20, None),
    ("Assinaturas", MatchOp.CONTAINS, "globoplay", 20, None),
    ("Assinaturas", MatchOp.CONTAINS, "max com", 30, None),
    # ---------- Compras/Marketplace ----------
    ("Compras/Marketplace", MatchOp.CONTAINS, "lojas americanas", 30, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "casa do celula", 30, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "calcados", 40, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "renner", 50, None),
    ("Compras/Marketplace", MatchOp.CONTAINS, "riachuelo", 50, None),
    # ---------- Cuidados pessoais (categoria é individual por padrão) ---------
    ("Cuidados pessoais", MatchOp.CONTAINS, "cosmetic", 40, None),
    ("Cuidados pessoais", MatchOp.CONTAINS, "makeup", 40, None),
    ("Cuidados pessoais", MatchOp.CONTAINS, "perfumaria", 40, None),
    ("Cuidados pessoais", MatchOp.CONTAINS, "barbearia", 40, None),
    ("Cuidados pessoais", MatchOp.CONTAINS, "cabeleireiro", 40, None),
    # ---------- Ensino ----------
    ("Ensino", MatchOp.CONTAINS, "pucrs", 20, None),
    ("Ensino", MatchOp.CONTAINS, "faculdade", 50, None),
    ("Ensino", MatchOp.CONTAINS, "universidade", 50, None),
    ("Ensino", MatchOp.CONTAINS, "udemy", 50, None),
    ("Ensino", MatchOp.CONTAINS, "alura", 50, None),
    # ============ 3ª rodada: conta Nubank + conta Itaú da Nayara ============
    # O Itaú escreve "PIX TRANSF <nome>" / "PIX QRS <merchant>" e TRUNCA a
    # descrição colando a data ("PIX QRS OFFICINA CA07/07"), então as regras
    # precisam casar prefixo, não o nome inteiro.
    # ---------- Ignorar: dinheiro que não sai do casal ----------
    # Nayara -> Lauro é acerto, não gasto (o lugar disso é a tela de Pagamentos).
    # Note o prefixo "pix": sem ele, "Wellhub Lauro Weingart" cairia aqui.
    ("Ignorado", MatchOp.CONTAINS, "pix transf lauro", 10, Split.IGNORED),
    ("Ignorado", MatchOp.CONTAINS, "pix lauro weingartner", 10, Split.IGNORED),
    # Nayara -> a própria conta dela no outro banco: transferência, não despesa.
    ("Ignorado", MatchOp.CONTAINS, "pix transf nayara", 10, Split.IGNORED),
    # ---------- Internet / telefonia ----------
    ("Internet", MatchOp.CONTAINS, "telefonica", 30, None),
    # \bvivo\b para não casar palavra que só contenha "vivo" no meio.
    ("Internet", MatchOp.REGEX, r"\bvivo\b", 30, None),
    ("Internet", MatchOp.CONTAINS, "claro s a", 50, None),
    ("Internet", MatchOp.CONTAINS, "tim s a", 50, None),
    # ---------- Restaurante/Delivery ----------
    # "officina" sozinho: o extrato do Itaú corta em "OFFICINA CA07/07".
    ("Restaurante/Delivery", MatchOp.CONTAINS, "officina", 20, None),
    # ---------- Farmácia ----------
    # Cremer: classificação que o próprio usuário deu na revisão do import.
    ("Farmácia", MatchOp.CONTAINS, "cremer", 30, None),
    # ---------- Outros: Pix do Itaú como último recurso ----------
    # Mesmo papel do fallback do Nubank: merchant conhecido casa antes (o Qtal
    # em p=20, a farmácia em p=15); só o Pix para pessoa física sobra aqui.
    ("Outros", MatchOp.CONTAINS, "pix transf", 90, None),
    ("Outros", MatchOp.CONTAINS, "pix qrs", 90, None),
    # ---------- Pix recorrentes para pessoas conhecidas ----------
    # Classificações que o usuário fez à mão na revisão do import; viram regra
    # porque são pessoas recorrentes. Prioridade 40 para ganhar do fallback
    # "todo Pix vira Outros" (p=90). Casam pelo sobrenome/nome composto, que é
    # o que distingue — e é o formato do Nubank, onde esses Pix acontecem.
    ("Lazer", MatchOp.CONTAINS, "nesvera", 40, None),
    ("Lazer", MatchOp.CONTAINS, "fabio henrique", 40, None),
    ("Cuidados pessoais", MatchOp.CONTAINS, "guski", 40, None),
]


async def ensure_categories() -> list[str]:
    """Cria as categorias novas que ainda não existem. Idempotente."""
    existing = {c["name"] for c in await cat_repo.list_categories()}
    created = []
    for spec in NEW_CATEGORIES:
        if spec["name"] not in existing:
            await cat_repo.create_category(spec)
            created.append(spec["name"])
    return created


async def _resolve_categories() -> dict[str, dict]:
    return {c["name"]: c for c in await cat_repo.list_categories()}


async def _build(cats: dict[str, dict]) -> list[dict]:
    out = []
    for name, op, value, priority, split in RULES:
        cat = cats.get(name)
        if cat is None:
            raise SystemExit(f"categoria não encontrada: {name!r}")
        resolved = split or (Split.SHARED if cat["is_shared_default"] else Split.INDIVIDUAL)
        out.append(
            {
                "matcher": {"field": "description", "op": op, "value": value},
                "category_id": cat["id"],
                "split_default": resolved,
                "priority": priority,
                "enabled": True,
                "_category_name": name,
            }
        )
    return out


async def simulate(specs: list[dict]) -> None:
    """Roda o rule engine contra os extratos de verdade, sem gravar nada."""
    engine = [
        Rule(
            id=str(i),
            field="description",
            op=s["matcher"]["op"],
            value=s["matcher"]["value"],
            category_id=s["category_id"],
            split_default=s["split_default"],
            priority=s["priority"],
        )
        for i, s in enumerate(specs)
    ]
    by_id = {s["category_id"]: s["_category_name"] for s in specs}
    rule_label = {
        str(i): f"{s['matcher']['op'].value}:{s['matcher']['value']}"
        for i, s in enumerate(specs)
    }

    txs = []
    for f in sorted(Path("../extratos").iterdir()):
        txs.extend(parse_file(f.name, f.read_bytes(), None))

    hits: dict[str, list] = {}
    misses = []
    for t in txs:
        m = classify(t.description, engine)
        if m:
            hits.setdefault(by_id[m.category_id], []).append((t, rule_label[m.rule_id]))
        else:
            misses.append(t)

    total = sum(t.amount_cents for t in txs)
    matched_cents = sum(t.amount_cents for t, _ in [x for v in hits.values() for x in v])
    print(f"=== {len(txs)} lançamentos, {format_brl(total)} ===")
    print(f"classificados: {len(txs) - len(misses)} ({format_brl(matched_cents)})")
    print(f"sem regra:     {len(misses)} ({format_brl(total - matched_cents)})\n")

    for cat in sorted(hits, key=lambda c: -sum(t.amount_cents for t, _ in hits[c])):
        items = hits[cat]
        cat_total = format_brl(sum(t.amount_cents for t, _ in items))
        print(f"── {cat}  ({len(items)} lanç., {cat_total})")
        for t, rule in sorted(items, key=lambda x: -x[0].amount_cents):
            print(f"     {format_brl(t.amount_cents):>12}  {t.description[:58]:<58} [{rule}]")

    print(f"\n── SEM REGRA ({len(misses)} lanç.)")
    for t in sorted(misses, key=lambda t: -t.amount_cents):
        print(f"     {format_brl(t.amount_cents):>12}  {t.description[:70]}")


async def apply(specs: list[dict]) -> None:
    """Sincroniza as regras: cria as que faltam, atualiza as que mudaram e
    remove as que foram substituídas. Idempotente."""
    db = get_db()

    removed = 0
    for op, value in OBSOLETE:
        result = await db.rules.delete_many({"matcher.op": op.value, "matcher.value": value})
        removed += result.deleted_count

    existing = {
        (r["matcher"]["op"], r["matcher"]["value"]): r for r in await rules_repo.list_rules()
    }
    created = updated = unchanged = 0
    for spec in specs:
        doc = {
            "matcher": {
                "field": "description",
                "op": spec["matcher"]["op"].value,
                "value": spec["matcher"]["value"],
            },
            "category_id": spec["category_id"],
            "split_default": spec["split_default"].value,
            "priority": spec["priority"],
            "enabled": True,
        }
        current = existing.get((doc["matcher"]["op"], doc["matcher"]["value"]))
        if current is None:
            await db.rules.insert_one(doc)
            created += 1
        elif any(current.get(k) != v for k, v in doc.items() if k != "matcher"):
            await db.rules.update_one({"_id": oid(current["id"])}, {"$set": doc})
            updated += 1
        else:
            unchanged += 1

    print(
        f"regras: {created} criadas, {updated} atualizadas, "
        f"{unchanged} sem mudança, {removed} removidas"
    )


async def main(do_apply: bool) -> None:
    if do_apply:
        created = await ensure_categories()
        if created:
            print(f"categorias criadas: {', '.join(created)}")
    cats = await _resolve_categories()
    missing = [c["name"] for c in NEW_CATEGORIES if c["name"] not in cats]
    if missing and not do_apply:
        print(f"(simulação) categorias que seriam criadas: {', '.join(missing)}\n")
        for spec in NEW_CATEGORIES:
            cats.setdefault(spec["name"], {"id": f"novo:{spec['name']}", **spec})
    specs = await _build(cats)
    if do_apply:
        await apply(specs)
    else:
        await simulate(specs)
        print("\nNada gravado. Rode com --apply para criar as regras.")
    close_client()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="grava as regras no Mongo")
    asyncio.run(main(parser.parse_args().apply))
