import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, EmptyState, Select, Spinner } from "@/components/ui";
import { api, formatBRL, type TrendPoint, type TrendReport } from "@/lib/api";
import {
  AXIS_TEXT,
  formatBRLAxis,
  GRID,
  MAX_SERIES,
  REFERENCE,
  RESIDUAL,
  SERIES,
  seriesColor,
  shortPeriod,
} from "@/lib/chartPalette";

const RESIDUAL_LABEL = "Demais categorias";
const WINDOWS = [6, 12, 24];

export function TrendSection() {
  const [months, setMonths] = useState(12);
  const { data, isLoading } = useQuery({
    queryKey: ["trend", months],
    queryFn: () => api.trend(months),
  });

  return (
    <section className="mt-10">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Evolução</h2>
          <p className="text-sm text-gray-500">
            Como os gastos variam mês a mês. Meses sem lançamento importado ficam fora.
          </p>
        </div>
        <Select
          className="w-44"
          value={String(months)}
          onChange={(e) => setMonths(Number(e.target.value))}
          aria-label="Janela de meses"
        >
          {WINDOWS.map((m) => (
            <option key={m} value={m}>
              Últimos {m} meses
            </option>
          ))}
        </Select>
      </div>

      {isLoading && <Spinner />}
      {data && data.points.length === 0 && (
        <EmptyState>Ainda não há meses com lançamentos.</EmptyState>
      )}
      {data && data.points.length > 0 && <TrendCharts data={data} />}
    </section>
  );
}

function TrendCharts({ data }: { data: TrendReport }) {
  const { points, average_total_cents: average } = data;

  // Nomes das pessoas na ordem em que o backend devolve — a cor segue a
  // pessoa, não a posição no ranking do mês.
  const people = useMemo(
    () => Array.from(new Map(points.flatMap((p) => p.users.map((u) => [u.user_id, u.name]))).values()),
    [points],
  );

  // Top categorias ganham cor própria; o resto soma no bucket residual.
  const topCategories = useMemo(() => data.categories.slice(0, MAX_SERIES), [data.categories]);

  const totalRows = useMemo(
    () => points.map((p) => ({ mes: shortPeriod(p.period), total: p.total_cents })),
    [points],
  );

  const peopleRows = useMemo(
    () =>
      points.map((p) => {
        const row: Record<string, string | number> = { mes: shortPeriod(p.period) };
        for (const u of p.users) row[u.name] = u.total_spent_cents;
        return row;
      }),
    [points],
  );

  const categoryRows = useMemo(
    () =>
      points.map((p) => {
        const row: Record<string, string | number> = { mes: shortPeriod(p.period) };
        let residual = 0;
        for (const c of p.by_category) {
          if (topCategories.includes(c.category_name)) {
            row[c.category_name] = ((row[c.category_name] as number) ?? 0) + c.total_cents;
          } else {
            residual += c.total_cents;
          }
        }
        if (residual > 0) row[RESIDUAL_LABEL] = residual;
        return row;
      }),
    [points, topCategories],
  );

  const last = points[points.length - 1];
  const previous = points.length > 1 ? points[points.length - 2] : null;
  const peak = points.reduce((a, b) => (b.total_cents > a.total_cents ? b : a));

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Stat label="Média mensal" value={formatBRL(average)} hint={`${points.length} meses`} />
        <DeltaStat last={last} previous={previous} />
        <Stat
          label="Mês mais caro"
          value={formatBRL(peak.total_cents)}
          hint={shortPeriod(peak.period)}
        />
      </div>

      <Card>
        <ChartTitle
          title="Gasto total por mês"
          subtitle="A linha tracejada é a média do período."
        />
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={totalRows} margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="mes" fontSize={11} tickLine={false} stroke={AXIS_TEXT} />
            <YAxis
              fontSize={11}
              tickLine={false}
              axisLine={false}
              stroke={AXIS_TEXT}
              tickFormatter={formatBRLAxis}
              width={78}
            />
            <Tooltip content={<MoneyTooltip />} cursor={{ fill: "rgba(0,0,0,0.035)" }} />
            <ReferenceLine
              y={average}
              stroke={REFERENCE}
              strokeDasharray="4 4"
              label={{ value: "média", position: "right", fill: AXIS_TEXT, fontSize: 11 }}
            />
            {/* Série única: sem legenda, o título já a nomeia. */}
            <Bar dataKey="total" name="Total" fill={SERIES[0]} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <ChartTitle title="Gasto por pessoa" subtitle="Compartilhado + individual de cada um." />
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={peopleRows} margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={GRID} />
              <XAxis dataKey="mes" fontSize={11} tickLine={false} stroke={AXIS_TEXT} />
              <YAxis
                fontSize={11}
                tickLine={false}
                axisLine={false}
                stroke={AXIS_TEXT}
                tickFormatter={formatBRLAxis}
                width={78}
              />
              <Tooltip content={<MoneyTooltip />} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
              {people.map((name, i) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={SERIES[i]}
                  strokeWidth={2}
                  dot={{ r: 3, strokeWidth: 0, fill: SERIES[i] }}
                  activeDot={{ r: 5, stroke: "#fff", strokeWidth: 2 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <ChartTitle
            title="Composição por categoria"
            subtitle={`As ${MAX_SERIES} maiores; o resto soma em "${RESIDUAL_LABEL}".`}
          />
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={categoryRows} margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={GRID} />
              <XAxis dataKey="mes" fontSize={11} tickLine={false} stroke={AXIS_TEXT} />
              <YAxis
                fontSize={11}
                tickLine={false}
                axisLine={false}
                stroke={AXIS_TEXT}
                tickFormatter={formatBRLAxis}
                width={78}
              />
              <Tooltip content={<MoneyTooltip />} cursor={{ fill: "rgba(0,0,0,0.035)" }} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
              {topCategories.map((name, i) => (
                // 2px de respiro entre os segmentos empilhados.
                <Bar
                  key={name}
                  dataKey={name}
                  stackId="cat"
                  fill={seriesColor(i)}
                  stroke="#fff"
                  strokeWidth={2}
                />
              ))}
              <Bar
                dataKey={RESIDUAL_LABEL}
                stackId="cat"
                fill={RESIDUAL}
                stroke="#fff"
                strokeWidth={2}
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <TrendTable points={points} topCategories={topCategories} />
    </div>
  );
}

function ChartTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="mb-4">
      <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
      <p className="text-xs text-gray-400">{subtitle}</p>
    </div>
  );
}

interface TooltipEntry {
  name?: string | number;
  value?: number;
  color?: string;
}

function MoneyTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((e) => typeof e.value === "number" && e.value !== 0);
  const total = rows.reduce((s, e) => s + (e.value ?? 0), 0);
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 text-xs shadow-lg">
      <div className="mb-1.5 font-semibold text-gray-900">{label}</div>
      {rows.map((e) => (
        <div key={String(e.name)} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-gray-600">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: e.color }}
            />
            {e.name}
          </span>
          <span className="font-medium text-gray-900">{formatBRL(e.value ?? 0)}</span>
        </div>
      ))}
      {rows.length > 1 && (
        <div className="mt-1.5 flex items-center justify-between gap-4 border-t border-gray-100 pt-1.5">
          <span className="text-gray-500">Total</span>
          <span className="font-semibold text-gray-900">{formatBRL(total)}</span>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-gray-900">{value}</div>
      {hint && <div className="mt-0.5 text-sm text-gray-400">{hint}</div>}
    </Card>
  );
}

function DeltaStat({ last, previous }: { last: TrendPoint; previous: TrendPoint | null }) {
  if (!previous) {
    return <Stat label="Variação no mês" value="—" hint="sem mês anterior para comparar" />;
  }
  const delta = last.total_cents - previous.total_cents;
  const pct = previous.total_cents > 0 ? (delta / previous.total_cents) * 100 : 0;
  const up = delta > 0;
  const flat = delta === 0;
  const Icon = flat ? Minus : up ? ArrowUpRight : ArrowDownRight;
  // Gastar mais é vermelho, gastar menos é verde — cor de status, com ícone
  // junto, nunca só a cor.
  const tone = flat ? "text-gray-500" : up ? "text-red-600" : "text-emerald-600";

  return (
    <Card>
      <div className="text-sm text-gray-500">
        Variação em {shortPeriod(last.period)}
      </div>
      <div className={`mt-1 flex items-center gap-1 text-xl font-semibold ${tone}`}>
        <Icon className="h-5 w-5" />
        {up ? "+" : ""}
        {formatBRL(delta)}
      </div>
      <div className="mt-0.5 text-sm text-gray-400">
        {pct >= 0 ? "+" : ""}
        {pct.toFixed(1)}% vs {shortPeriod(previous.period)}
      </div>
    </Card>
  );
}

/** Alternativa em tabela: exigida porque três cores da paleta ficam abaixo de
 *  3:1 de contraste com o fundo claro. */
function TrendTable({
  points,
  topCategories,
}: {
  points: TrendPoint[];
  topCategories: string[];
}) {
  const [open, setOpen] = useState(false);
  const people = Array.from(
    new Map(points.flatMap((p) => p.users.map((u) => [u.user_id, u.name]))).values(),
  );

  /** Valor de uma categoria no mês; `null` soma tudo que ficou no residual. */
  const catValue = (p: TrendPoint, name: string | null): number =>
    p.by_category
      .filter((c) =>
        name === null ? !topCategories.includes(c.category_name) : c.category_name === name,
      )
      .reduce((s, c) => s + c.total_cents, 0);

  return (
    <Card className="overflow-hidden p-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full px-4 py-3 text-left text-sm font-medium text-gray-600 hover:bg-gray-50"
      >
        {open ? "Ocultar" : "Ver"} os números em tabela
      </button>
      {open && (
        <div className="overflow-x-auto border-t border-gray-100">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Mês</th>
                {people.map((n) => (
                  <th key={n} className="px-4 py-3 text-right">
                    {n}
                  </th>
                ))}
                <th className="px-4 py-3 text-right">Compartilhado</th>
                <th className="px-4 py-3 text-right">Individual</th>
                <th className="px-4 py-3 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {[...points].reverse().map((p) => (
                <tr key={p.period} className="border-b border-gray-50">
                  <td className="whitespace-nowrap px-4 py-2 text-gray-500">
                    {shortPeriod(p.period)}
                  </td>
                  {people.map((n) => {
                    const u = p.users.find((x) => x.name === n);
                    return (
                      <td key={n} className="whitespace-nowrap px-4 py-2 text-right text-gray-700">
                        {formatBRL(u?.total_spent_cents ?? 0)}
                      </td>
                    );
                  })}
                  <td className="whitespace-nowrap px-4 py-2 text-right text-gray-700">
                    {formatBRL(p.shared_total_cents)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-right text-gray-700">
                    {formatBRL(p.individual_total_cents)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-right font-semibold text-gray-900">
                    {formatBRL(p.total_cents)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Mesmos números do gráfico empilhado. Existe porque três cores da
              paleta ficam abaixo de 3:1 no fundo claro — a regra de alívio
              exige rótulo visível ou tabela. */}
          <table className="w-full border-t border-gray-100 text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Mês</th>
                {topCategories.map((c) => (
                  <th key={c} className="whitespace-nowrap px-4 py-3 text-right">
                    {c}
                  </th>
                ))}
                <th className="whitespace-nowrap px-4 py-3 text-right">{RESIDUAL_LABEL}</th>
              </tr>
            </thead>
            <tbody>
              {[...points].reverse().map((p) => (
                <tr key={p.period} className="border-b border-gray-50">
                  <td className="whitespace-nowrap px-4 py-2 text-gray-500">
                    {shortPeriod(p.period)}
                  </td>
                  {topCategories.map((c) => (
                    <td key={c} className="whitespace-nowrap px-4 py-2 text-right text-gray-700">
                      {formatBRL(catValue(p, c))}
                    </td>
                  ))}
                  <td className="whitespace-nowrap px-4 py-2 text-right text-gray-700">
                    {formatBRL(catValue(p, null))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
