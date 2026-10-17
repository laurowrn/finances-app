/**
 * Money pattern no frontend: todo valor monetário é um inteiro de centavos.
 *
 * O backend fala centavos (campos `*_cents`) e o JSON carrega inteiros, que são
 * exatos em JavaScript até 2^53 — bem além de qualquer valor deste app. Float
 * só apareceria se a gente dividisse por 100, então nada aqui divide: a
 * formatação é feita com aritmética inteira, e o parse do input vem da string.
 */

/** Valor monetário em centavos. Alias de number — documenta a intenção. */
export type Cents = number;

/** Centavos -> "R$ 1.234,56". Só inteiros, sem divisão em ponto flutuante. */
export function formatBRL(cents: Cents): string {
  const negative = cents < 0;
  const abs = Math.abs(Math.round(cents));
  const reais = Math.floor(abs / 100);
  const centavos = abs % 100;
  const inteiro = new Intl.NumberFormat("pt-BR").format(reais);
  return `${negative ? "-" : ""}R$ ${inteiro},${String(centavos).padStart(2, "0")}`;
}

/**
 * Texto digitado -> centavos. `null` se não for um número válido.
 *
 * Trabalha sobre a string em vez de `Number(x) * 100` de propósito:
 * `Number("12275.19") * 100` dá 1227518.9999999998. Aqui o resultado é exato.
 * Aceita "1234,56" e "1234.56"; mais de 2 casas é truncado (centavo é o menor
 * valor que existe).
 */
export function parseBRLToCents(text: string): Cents | null {
  const cleaned = (text ?? "").trim().replace(/[R$\s ]/g, "");
  if (!cleaned) return null;

  const match = /^([+-]?)(\d*)(?:[.,](\d*))?$/.exec(cleaned);
  if (!match) return null;

  const [, sign, whole, frac = ""] = match;
  if (!whole && !frac) return null;

  const centavos = (frac + "00").slice(0, 2);
  const cents = Number(whole || "0") * 100 + Number(centavos);
  return sign === "-" ? -cents : cents;
}

/**
 * Centavos -> valor para `<input type="number" step="0.01">`, que espera
 * ponto como separador decimal. String vazia para null/undefined.
 */
export function centsToInput(cents: Cents | null | undefined): string {
  if (cents === null || cents === undefined) return "";
  const negative = cents < 0;
  const abs = Math.abs(cents);
  return `${negative ? "-" : ""}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}
