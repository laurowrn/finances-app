/**
 * Paleta categórica dos gráficos — validada, não escolhida no olho.
 *
 * A paleta anterior do app (indigo/ciano/âmbar/esmeralda/rosa/violeta/cinza)
 * reprovava em dois pontos: rosa (#ec4899) e esmeralda (#10b981) ficavam com
 * ΔE 4,9 sob deuteranopia — indistinguíveis para quem tem daltonismo
 * vermelho-verde — e o cinza (#94a3b8) ficava abaixo do piso de croma, lendo
 * como "sem cor" em vez de como uma série.
 *
 * Esta ordem passa em todos os testes para pares adjacentes (barras
 * empilhadas, linhas): pior ΔE CVD 9,1 e pior ΔE visão normal 19,6.
 *
 * Regras que valem ao mexer aqui:
 * - As cores são atribuídas em ordem fixa e nunca cicladas. Uma 8ª série não
 *   ganha cor nova: vira `RESIDUAL`.
 * - A cor segue a entidade, não a posição no ranking — filtrar não repinta.
 * - Três slots (aqua, amarelo, magenta) ficam abaixo de 3:1 de contraste com o
 *   fundo claro, então todo gráfico que os usa precisa de legenda e tooltip.
 */

/** Ordem fixa das séries. Nunca cicle; nunca gere uma cor nova. */
export const SERIES = [
  "#2a78d6", // azul
  "#eb6834", // laranja
  "#1baf7a", // aqua
  "#eda100", // amarelo
  "#e87ba4", // magenta
  "#008300", // verde
  "#4a3aa7", // violeta
] as const;

/** Bucket residual ("Demais categorias"). Cinza de propósito: não é identidade. */
export const RESIDUAL = "#9a9a93";

export const GRID = "#ececeb";
export const AXIS_TEXT = "#52514e";
export const REFERENCE = "#8a8982";

/** Quantas categorias ganham cor própria antes de cair no bucket residual. */
export const MAX_SERIES = SERIES.length - 1;

export function seriesColor(index: number): string {
  return index < MAX_SERIES ? SERIES[index] : RESIDUAL;
}

/**
 * Rótulo curto para eixo de valor: "R$ 15,3 mil". Só para tick de eixo —
 * tooltip e rótulo direto usam `formatBRL`, que é exato em centavos.
 */
export function formatBRLAxis(cents: number): string {
  const reais = Math.round(cents / 100);
  if (Math.abs(reais) >= 1000) {
    const mil = reais / 1000;
    const casas = Math.abs(reais) % 1000 === 0 ? 0 : 1;
    return `R$ ${mil.toFixed(casas).replace(".", ",")} mil`;
  }
  return `R$ ${reais}`;
}

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/** "2026-07" -> "jul/26" */
export function shortPeriod(period: string): string {
  const [y, m] = period.split("-").map(Number);
  return `${MESES[m - 1]}/${String(y).slice(2)}`;
}
