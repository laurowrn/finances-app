import { ChevronLeft, ChevronRight } from "lucide-react";

const MONTHS = [
  "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
  "Jul", "Ago", "Set", "Out", "Nov", "Dez",
];

function shift(period: string, delta: number): string {
  const [y, m] = period.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function label(period: string): string {
  const [y, m] = period.split("-").map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}

export function PeriodPicker({
  period,
  onChange,
}: {
  period: string;
  onChange: (p: string) => void;
}) {
  return (
    <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-white p-1">
      <button
        className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100"
        onClick={() => onChange(shift(period, -1))}
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      <span className="min-w-24 text-center text-sm font-medium text-gray-800">
        {label(period)}
      </span>
      <button
        className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100"
        onClick={() => onChange(shift(period, 1))}
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}
