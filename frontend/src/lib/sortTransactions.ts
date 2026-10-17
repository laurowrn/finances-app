import type { Transaction } from "@/lib/api";
import { SPLIT_LABEL, toSplitState } from "@/lib/split";

export type SortKey = "date" | "description" | "owner" | "category" | "split" | "amount";
export interface Sort {
  key: SortKey;
  dir: "asc" | "desc";
}

/**
 * Direção inicial ao clicar numa coluna que ainda não está ordenada.
 * Data e valor abrem no mais recente / mais caro; texto abre em A→Z.
 */
export function initialDir(key: SortKey): Sort["dir"] {
  return key === "date" || key === "amount" ? "desc" : "asc";
}

export function nextSort(current: Sort, key: SortKey): Sort {
  if (current.key === key) {
    return { key, dir: current.dir === "asc" ? "desc" : "asc" };
  }
  return { key, dir: initialDir(key) };
}

/**
 * Ordena a lista já filtrada pelo período.
 *
 * Colunas de texto ordenam pelo rótulo que aparece na tela (nome da pessoa, da
 * categoria) e não pelo id — ordenar por ObjectId não diria nada a quem lê.
 * `localeCompare` em pt-BR para acento não jogar "Ó" depois de "Z".
 */
export function sortTransactions(
  txs: Transaction[],
  sort: Sort,
  userName: Record<string, string>,
  categoryName: Record<string, string>,
): Transaction[] {
  const text = (t: Transaction): string => {
    switch (sort.key) {
      case "description":
        return t.description;
      case "owner":
        return userName[t.owner_user_id] ?? "";
      case "category":
        return t.category_id ? (categoryName[t.category_id] ?? "") : "";
      case "split":
        return SPLIT_LABEL[toSplitState(t)];
      default:
        return "";
    }
  };

  const compare = (a: Transaction, b: Transaction): number => {
    if (sort.key === "amount") return a.amount_cents - b.amount_cents;
    if (sort.key === "date") return a.date.localeCompare(b.date); // ISO ordena como texto
    const [x, y] = [text(a), text(b)];
    // "Sem categoria" vai para o fim em asc, para não competir com nomes reais.
    if (!x && y) return 1;
    if (x && !y) return -1;
    return x.localeCompare(y, "pt-BR");
  };

  // Desempate estável por data desc, para a ordem não "tremer" entre renders.
  return [...txs].sort((a, b) => {
    const r = compare(a, b);
    if (r !== 0) return sort.dir === "asc" ? r : -r;
    return b.date.localeCompare(a.date);
  });
}
