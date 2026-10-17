/**
 * Como um gasto entra na conta do casal: compartilhado, individual ou ignorado.
 *
 * "Ignorado" existe porque o extrato da conta e a fatura do cartão se sobrepõem
 * — o "Pagamento de fatura" no extrato é a mesma despesa das compras da fatura.
 * O lançamento continua no histórico, mas fica fora do relatório e do acerto.
 *
 * Na transação isso vive em duas flags (`is_shared` / `is_ignored`), porque
 * ignorado não é nem compartilhado nem individual. Aqui elas viram um valor só,
 * que é como as telas mostram e alternam.
 */

export type SplitState = "shared" | "individual" | "ignored";

export interface SplitFlags {
  is_shared: boolean;
  is_ignored: boolean;
}

export function toSplitState({ is_shared, is_ignored }: SplitFlags): SplitState {
  if (is_ignored) return "ignored";
  return is_shared ? "shared" : "individual";
}

export function toSplitFlags(state: SplitState): SplitFlags {
  return {
    is_shared: state === "shared",
    is_ignored: state === "ignored",
  };
}

/** Ordem do clique no badge: compartilhado -> individual -> ignorado -> ... */
export function nextSplitState(state: SplitState): SplitState {
  if (state === "shared") return "individual";
  if (state === "individual") return "ignored";
  return "shared";
}

export const SPLIT_LABEL: Record<SplitState, string> = {
  shared: "Compartilhado",
  individual: "Individual",
  ignored: "Ignorado",
};

export const SPLIT_TONE: Record<SplitState, "indigo" | "gray" | "amber"> = {
  shared: "indigo",
  individual: "gray",
  ignored: "amber",
};
